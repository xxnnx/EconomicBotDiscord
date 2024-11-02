import disnake
from disnake.ext import commands, tasks
from disnake.ui import Button, View, Select, Modal, TextInput
from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji
import io
import requests
import datetime
import time
import os
import sqlite3
from config import settings

intents = disnake.Intents.all()

bot = commands.Bot(command_prefix = settings['prefix'], intents = intents)
bot.remove_command('help')


connection = sqlite3.connect('server.db')
cursor = connection.cursor()

# Словарь для хранения времени нахождения пользователя в голосовом чате
voice_time_tracking = {}
# Частота начислений в минутах
reward_interval_minutes = 5
# Награда за интервал (в листиках)
reward_per_interval = 10

TICKET_CHANNEL_ID = 1299473325327777802
ticket_admin_messages = {}
date = datetime.datetime.now().time()

last_ctx = None
last_message = None

@bot.event #Код чтобы бот игнорировал команды которые ему пишут в личные сообщения
async def on_message(message):
    # Игнорируем сообщения от бота
    if message.author == bot.user:
        return
        
    # Проверяем, если сообщение в ЛС
    if isinstance(message.channel, disnake.DMChannel):
        await message.channel.send("Я игнорирую команды от других пользователей в ЛС.")
        return

    # Обрабатываем команды
    await bot.process_commands(message)

@bot.event
async def on_ready():
    if not reward_voice_chat_users.is_running():
        reward_voice_chat_users.start()
    print('Bot connected and voice reward system initialized')

    channel = bot.get_channel(1299473325327777802) #ID канала куда бот будет присылать кнопку для создания тикета
    if channel:
        await channel.purge(limit=100)
        message = await channel.send("Инициализация команды..")
        ctx = await bot.get_context(message)

        await ticket(ctx)

        await message.delete()

    cursor.execute("""CREATE TABLE IF NOT EXISTS users (
        name TEXT,
        id INT,
        cash BIGINT,
        rep INT,
        server_id INT
    )""")
    connection.commit()

    for guild in bot.guilds:
        for member in guild.members:
            if cursor.execute(f"SELECT id FROM users WHERE id = {member.id}").fetchone() is None:
                cursor.execute(f"INSERT INTO users VALUES ('{member}',{member.id},0,0, {guild.id})")
                connection.commit()
            else:
                pass

    connection.commit()
    await bot.change_presence(activity = disnake.Activity(name = f'!help 👨‍⚖️', type = disnake.ActivityType.playing))

@bot.event
async def on_member_join(member):
    if cursor.execute(f"SELECT id FROM users WHERE id = {member.id}").fetchone() is None:
        cursor.execute(f"INSERT INTO users VALUES ('{member}',{member.id},0,0, {member.guild.id})")
        connection.commit()
    else:
        pass

@tasks.loop(minutes=reward_interval_minutes)
async def reward_voice_chat_users():
    current_time = datetime.datetime.now()

    for guild in bot.guilds:
        for channel in guild.voice_channels:
            for member in channel.members:
                if member.id in voice_time_tracking:
                    voice_time_tracking[member.id] += reward_interval_minutes
                else:
                    voice_time_tracking[member.id] = reward_interval_minutes
                
                if voice_time_tracking[member.id] >= reward_interval_minutes:
                    cursor.execute("UPDATE users SET cash = cash + ? WHERE id = ?", (reward_per_interval, member.id))
                    connection.commit()

    print(f"[{current_time}] Начислены листики за голосовой чат")

@bot.command(aliases=['balance'])
async def __balance(ctx, member: disnake.Member = None):
    if member is None:
        member = ctx.author

    # Получаем данные пользователя
    user_balance = cursor.execute("SELECT cash FROM users WHERE id = ?", (member.id,)).fetchone()[0]
    user_name = str(member)

    # Получаем аватарку пользователя
    avatar_bytes = await member.avatar.read()
    avatar_image = Image.open(io.BytesIO(avatar_bytes))
    avatar_image = avatar_image.resize((100, 100))

    # Создаем маску для круглой аватарки
    mask = Image.new("L", (100, 100), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse((0, 0, 100, 100), fill=255)
    avatar_image = avatar_image.convert("RGBA")
    avatar_image.putalpha(mask)

    # Создаем основное изображение
    width, height = 400, 200
    background_color = (30, 30, 30)
    text_color = (255, 255, 255)
    img = Image.new("RGB", (width, height), color=background_color)
    draw = ImageDraw.Draw(img)

    # Задаем шрифт
    try:
        font = ImageFont.truetype('arial.ttf', 20)
    except IOError:
        font = ImageFont.load_default()

    # Вставляем круглую аватарку и текст
    img.paste(avatar_image, (20, 55), avatar_image)
    text_balance = f"Баланс: {user_balance} 🍃"
    text_user = f"Пользователь: {user_name}"
    with Pilmoji(img) as pilmoji:
        pilmoji.text((150, 55), text_user, fill=text_color, font=font)
        pilmoji.text((150, 130), text_balance, fill=text_color, font=font)

    # Сохраняем изображение в байтовый поток
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    # Создаем кнопки для магазина и перевода
    button_shop = Button(label="Открыть магазин", style=disnake.ButtonStyle.green)
    button_transfer = Button(label="Перевод", style=disnake.ButtonStyle.blurple)

    # Обработчик кнопки "Открыть магазин"
    async def button_shop_callback(interaction: disnake.MessageInteraction):
        await show_shop(interaction)  # Вызываем функцию show_shop

    # Привязываем обработчик к кнопке магазина
    button_shop.callback = button_shop_callback

    # Обработчик кнопки "Перевод"
    async def button_transfer_callback(interaction: disnake.MessageInteraction):
        # Удаляем сообщение с изображением и кнопками
        await interaction.message.delete()
        # Открываем меню перевода
        await open_transfer_menu(interaction)

    # Привязываем обработчик к кнопке перевода
    button_transfer.callback = button_transfer_callback

    # Добавляем кнопки в представление и отправляем изображение
    view = View()
    view.add_item(button_shop)
    view.add_item(button_transfer)
    await ctx.send(file=disnake.File(buffer, "balance.png"), view=view)

# Функция для открытия меню перевода
async def open_transfer_menu(interaction):
    # Проверяем баланс пользователя
    sender_balance = cursor.execute("SELECT cash FROM users WHERE id = ?", (interaction.user.id,)).fetchone()[0]
    if sender_balance <= 0:
        await interaction.response.send_message("Недостаточно средств для перевода.", ephemeral=True)
        return

    # Получаем список пользователей сервера (до 25 пользователей)
    members = [member for member in interaction.guild.members if not member.bot]
    if len(members) > 25:
        members = members[:25]  # Ограничиваем до 25

    # Создаем выпадающее меню с пользователями сервера
    select_menu = Select(
        placeholder="Выберите пользователя для перевода",
        options=[
            disnake.SelectOption(label=member.display_name, value=str(member.id))
            for member in members
        ]
    )

    async def select_callback(interaction):
        selected_user_id = int(select_menu.values[0])
        await interaction.message.delete()
        await request_transfer_amount(interaction, selected_user_id)

    select_menu.callback = select_callback

    view = View()
    view.add_item(select_menu)
    await interaction.response.send_message("Выберите пользователя для перевода:", view=view)

# Функция для запроса суммы перевода
async def request_transfer_amount(interaction, selected_user_id):
    # Создаем модальное окно для ввода суммы
    class TransferModal(Modal):
        def __init__(self):
            # Создаем поле для ввода суммы перевода с уникальным `custom_id`
            amount_input = TextInput(
                label="Сумма", 
                placeholder="Введите сумму", 
                required=True, 
                max_length=10, 
                custom_id="transfer_amount_input"
            )
            super().__init__(title="Введите сумму перевода", components=[amount_input])
            self.amount_input = amount_input

        async def callback(self, interaction):
            # Используем interaction.text_values для получения значения
            transfer_amount_str = interaction.text_values["transfer_amount_input"]
            if transfer_amount_str.isdigit():
                transfer_amount = int(transfer_amount_str)
                
                # Проверка баланса отправителя перед переводом
                sender_balance = cursor.execute("SELECT cash FROM users WHERE id = ?", (interaction.user.id,)).fetchone()[0]
                if sender_balance < transfer_amount:
                    await interaction.response.send_message("Недостаточно средств для перевода.", ephemeral=True)
                    return
                
                # Логика перевода (обновление базы данных)
                cursor.execute("UPDATE users SET cash = cash - ? WHERE id = ?", (transfer_amount, interaction.user.id))
                cursor.execute("UPDATE users SET cash = cash + ? WHERE id = ?", (transfer_amount, selected_user_id))
                await interaction.response.send_message(f"Переведено {transfer_amount} 🍃 пользователю <@{selected_user_id}>")
            else:
                await interaction.response.send_message("Введите корректную сумму для перевода.", ephemeral=True)

    modal = TransferModal()
    await interaction.response.send_modal(modal)

# Функция для отображения магазина
async def show_shop(interaction):
    embed = disnake.Embed(title="Магазин ролей", description="Доступные роли для покупки")
    
    for role_name, role_info in roles_shop.items():
        embed.add_field(
            name=role_name,
            value=f"Цена: {role_info['cost']} 🍃",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)

@bot.command(aliases = ['award'])
async def __award(ctx, member: disnake.Member = None, amount: int = None):
    if ctx.message.author.guild_permissions.administrator:
        if member is None:
            await ctx.send(f"**{ctx.author}**, укажите пользователя, которому желаете выдать определнную сумму")
        else:
            if amount is None:
                await ctx.send(f"**{ctx.author}**, укажите сумму, которую желаете начислить на счет пользователя")
            elif amount < 1:
                await ctx.send(f"*{ctx.author}**, укажите сумму больше 1")
            else:
                cursor.execute("UPDATE users SET cash = cash + {} WHERE id = {}".format(amount,member.id))
                await member.send(f'Привет **{member.name}**, **{bot.user.name}** засчислил вам листиков. Ваш баланс: **{cursor.execute("SELECT cash FROM users WHERE id = {}".format(member.id)).fetchone()[0]}** :leaves:')
                connection.commit()

                await ctx.message.add_reaction('✅')
    else:
        await ctx.send(f"**Отказано в доступе**")

@bot.command(aliases = ['deprive'])
async def __deprive(ctx, member: disnake.Member = None, amount = None):
    if ctx.message.author.guild_permissions.administrator:
        if member is None:
            await ctx.send(f"**{ctx.author}**, укажите пользователя, у которого желаете забрать определнную сумму")
        else:
            if amount is None:
                await ctx.send(f"**{ctx.author}**, укажите сумму, которую желаете забрать со счета пользователя")
            elif int(amount) < 1:
                await ctx.send(f"*{ctx.author}**, укажите сумму больше 1")
            else:
                cursor.execute("UPDATE users SET cash = cash - {} WHERE id = {}".format(int(amount),member.id))
                connection.commit()

                await ctx.message.add_reaction('✅')

@bot.command(aliases = ['leaderboard', 'lb'])
async def __leaderboard(ctx):
    embed = disnake.Embed(title = 'Топ 10 сервера')
    counter = 0

    for row in cursor.execute("SELECT name, cash FROM users WHERE server_id = {} ORDER BY cash DESC LIMIT 10".format(ctx.guild.id)):
        counter += 1
        embed.add_field(
            name = f'# {counter} | `{row[0]}`',
            value = f'Баланс: {row[1]}',
            inline = False
            )

    await ctx.send(embed = embed)

@bot.command(pass_context = True)
async def help(ctx):
    emb = disnake.Embed(title = '**Навигация по командам сервера** :leaves:', color = 0x95a5a6)
    emb.set_author(name = bot.user.name, icon_url = bot.user.avatar)

    emb.add_field(name = '**!balance**', value = 'Проверить баланс любого пользователя')
    emb.add_field(name = '**!award**', value = 'Выдать награждение пользователю')
    emb.add_field(name = '**!deprive**', value = 'Отобрать любое количество валюты') 
    emb.add_field(name = '**!leaderboard**', value = 'Посмотерть топ 10 сервера по балансу')
    emb.add_field(name = '**Ticket**', value = 'Вы так же можете открыть тикет в чате <#1299473325327777802>')
    emb.set_footer(text = "мяу")


    await ctx.send(embed = emb,
        components = [
            disnake.ui.Button(style = disnake.ButtonStyle.grey, label = "Нужна помощь?", custom_id = "Нужна помощь?")
        ],
        )

    await ctx.message.add_reaction('✅')

@bot.listen("on_button_click")
async def help_listener(inter: disnake.MessageInteraction):
    if inter.component.custom_id not in ["Нужна помощь?"]:
        return

    if inter.component.custom_id == "Нужна помощь?":
        await inter.response.send_message("Contact <@650306540179292160>")

roles_shop = {
    "сок-rich": {"cost": 1000, "role_id": 1300142132576784506}
}

@bot.command()
async def shop(ctx):
    embed = disnake.Embed(title="Магазин ролей", description="Доступные роли для покупки")
    print('[',date,']','Открыт магазин')
    
    for role_name, role_info in roles_shop.items():
        embed.add_field(
            name=role_name,
            value=f"Цена: {role_info['cost']} :leaves:",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command()
async def buy(ctx, role_name: str = None):
    if role_name is None:
        await ctx.send(f"**{ctx.author}**, укажите название роли, которую хотите купить. Используйте команду `!shop` для просмотра доступных ролей.")
        print('[',date,']','При вызове команды buy не написали название роли')
        return
    
    # Проверка, существует ли указанная роль в магазине
    if role_name not in roles_shop:
        await ctx.send(f"**{ctx.author}**, роль '{role_name}' не найдена в магазине. Проверьте название.")
        print('[',date,']','Роль не куплена, не найдена в магазине')
        return

    role_info = roles_shop[role_name]
    role_cost = role_info["cost"]
    role_id = role_info["role_id"]

    # Проверка баланса пользователя
    user_balance = cursor.execute("SELECT cash FROM users WHERE id = ?", (ctx.author.id,)).fetchone()
    if user_balance is None or user_balance[0] < role_cost:
        await ctx.send(f"**{ctx.author}**, у вас недостаточно :leaves: для покупки роли '{role_name}'.")
        print('[',date,']','Роль не куплена, нехватает листиков')
        return

    # Проверка, есть ли у пользователя уже эта роль
    role = ctx.guild.get_role(role_id)
    if role in ctx.author.roles:
        await ctx.send(f"**{ctx.author}**, у вас уже есть роль '{role_name}'.")
        print('[',date,']','Роль не куплена, у пользователя уже есть эта роль')
        return

    # Списание средств и выдача роли
    cursor.execute("UPDATE users SET cash = cash - ? WHERE id = ?", (role_cost, ctx.author.id))
    connection.commit()
    await ctx.author.add_roles(role)
    
    await ctx.send(f"**{ctx.author}**, вы успешно купили роль '{role_name}' за {role_cost} :leaves:!")
    print('[',date,']','Роль куплена')

class MyModal(disnake.ui.Modal): # Создание модального окна
    def __init__(self):
        components = [
            disnake.ui.TextInput(
                label="Описание",
                placeholder="Что случилось?",
                custom_id="description",
                style=disnake.TextInputStyle.paragraph,
            ),
        ]
        super().__init__(
            title="Создание тикета",
            custom_id="create_ticket_modal",
            components=components,
        )

    async def callback(self, inter: disnake.ModalInteraction):
        description = inter.text_values["description"]

        guild = inter.guild
        role_name = f"Ticket-{inter.user.id}"
        # Создание роли для тикета
        role = await guild.create_role(name=role_name)
        await inter.user.add_roles(role)
        overwrites = {
            guild.default_role: disnake.PermissionOverwrite(read_messages=False),
            inter.user: disnake.PermissionOverwrite(read_messages=True),
            role: disnake.PermissionOverwrite(read_messages=True)
        }
        # Создание канала
        channel_name = f'ticket-{inter.user.id}'
        channel = await guild.create_text_channel(channel_name, overwrites=overwrites)

        # Создание embed
        embed = disnake.Embed(title="Ваш тикет", description=description, color=disnake.Color.blue())
        embed.add_field(name="Создан пользователем", value=inter.user.mention)

        await channel.send(embed=embed)
        await channel.send(f'Привет {inter.user.mention}, администратор ответит вам в ближайшее время')

        # Кнопка закрытия тикета
        close_button = disnake.ui.Button(label="Закрыть", style=disnake.ButtonStyle.red, custom_id=f'close_ticket-{inter.user.id}')
        close_view = disnake.ui.View()
        close_view.add_item(close_button)

        await channel.send("Нажмите кнопку ниже, чтобы закрыть тикет:", view=close_view)
        await inter.response.send_message(f'Тикет создан: {channel.mention}', ephemeral=True)

        # Отправка в админ канал сообщения что создан тикет
        admin_channel = guild.get_channel(1300843234750234675)
        admin_embed = disnake.Embed(title="Новая заявка", description=f"От {inter.user.mention}", color=disnake.Color.green())
        admin_embed.add_field(name="Жалоба/Причина", value=description)

        # Кнопка принятия тикета для админа
        accept_button = disnake.ui.Button(label="Принять", style=disnake.ButtonStyle.green, custom_id=f'accept_ticket-{inter.user.id}')
        accept_view = disnake.ui.View()
        accept_view.add_item(accept_button)

        admin_message = await admin_channel.send(embed=admin_embed, view=accept_view)
        ticket_admin_messages[inter.user.id] = admin_message.id

def create_ticket_view(): # Создание кнопки для тикета
    button = disnake.ui.Button(label="Создать тикет", style=disnake.ButtonStyle.primary, custom_id="create_ticket")
    view = disnake.ui.View()
    view.add_item(button)

    async def button_callback(interaction):
        existing_tickets = [channel for channel in interaction.guild.channels if channel.name.startswith(f'ticket-{interaction.user.id}')]

        if existing_tickets:
            await interaction.response.send_message("Вы уже открыли тикет. Пожалуйста, закройте его перед созданием нового.", ephemeral=True)
            return

        modal = MyModal()
        await interaction.response.send_modal(modal)

    button.callback = button_callback
    return view

@bot.command()
async def ticket(ctx): # Создание текста и запуск создания кнопки
    global last_ctx, last_message
    last_ctx = ctx  # Сохраняем текущий контекст

    # Создаём вид с кнопкой для первого сообщения
    view = create_ticket_view()
    if last_message:
        # Если сообщение уже существует, обновляем только кнопку
        await last_message.edit(view=view)
    else:
        last_message = await ctx.send("Нажмите кнопку ниже для создания тикета:", view=view)

    # Проверка запущена ли задача обновления кнопки
    if not refresh_ticket_button.is_running():
        refresh_ticket_button.start()

@tasks.loop(minutes=4)
async def refresh_ticket_button(): # Каждый 4 минут обновление кнопки
    global last_message
    if last_message:
        print('[',date,']',"Обновляем кнопку в сообщении")
        new_view = create_ticket_view()
        await last_message.edit(view=new_view)  # Обновляем только кнопку

@bot.event
async def on_interaction(interaction):
    try:
        # Closing the ticket
        if interaction.data['custom_id'].startswith('close_ticket-'):
            user_id = interaction.data['custom_id'].split('-')[1]
            
            if interaction.user.id == int(user_id) or disnake.utils.get(interaction.user.roles, id=1300843105532117002):
                channel = interaction.channel
                role_name = f"Ticket-{user_id}"
                role = disnake.utils.get(interaction.guild.roles, name=role_name)

                if role:
                    # Fetching the ticket creator to remove the role
                    ticket_creator = await interaction.guild.fetch_member(int(user_id))
                    await ticket_creator.remove_roles(role)
                    
                    # Removing the role from the admin who is closing the ticket
                    await interaction.user.remove_roles(role)

                    # Deleting the role
                    await role.delete()

                await interaction.response.send_message(f'Тикет {channel.mention} закрыт.', ephemeral=True)
                await channel.delete()
            else:
                await interaction.response.send_message("У вас нет прав на закрытие этого тикета.", ephemeral=True)

        # Accepting the ticket
        elif interaction.data['custom_id'].startswith('accept_ticket-'):
            user_id = interaction.data['custom_id'].split('-')[1]
            user = await interaction.guild.fetch_member(int(user_id))
            role_name = f"Ticket-{user_id}"
            role = disnake.utils.get(interaction.guild.roles, name=role_name)

            if not role:
                await interaction.response.send_message("Роль для этого тикета не найдена.", ephemeral=True)
                return

            await interaction.user.add_roles(role)

            # Granting admin access to the ticket channel
            ticket_channel = disnake.utils.get(interaction.guild.channels, name=f'ticket-{user_id}')
            if ticket_channel:
                await ticket_channel.set_permissions(interaction.user, read_messages=True)
                await interaction.response.send_message(f'Вы приняли тикет и получили доступ к {ticket_channel.mention}.', ephemeral=True)

                # Retrieve the admin message to update
                admin_channel = interaction.guild.get_channel(1300843234750234675)  # Replace with admin channel ID
                admin_message_id = ticket_admin_messages.get(int(user_id))
                
                if admin_message_id:
                    admin_message = await admin_channel.fetch_message(admin_message_id)
                    # Updating embed to show who accepted the ticket
                    updated_embed = admin_message.embeds[0]
                    updated_embed.add_field(name="Принят администратором", value=interaction.user.mention, inline=False)

                    # Removing the "Принять" button
                    new_view = disnake.ui.View()

                    # Editing the admin message to reflect the acceptance
                    await admin_message.edit(embed=updated_embed, view=new_view)
            else:
                await interaction.response.send_message("Канал для этого тикета не найден.", ephemeral=True)

    except Exception as e:
        print(f"Ошибка в on_interaction: {e}")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def status(ctx): #Команда status
    open_tickets = [channel for channel in ctx.guild.channels if channel.name.startswith('ticket-')]
    
    if not open_tickets:
        await ctx.send("Нет открытых тикетов.")
        return

    status_message = "Открытые тикеты:\n" + "\n".join([f"{channel.mention} - {channel.name}" for channel in open_tickets])
    await ctx.send(status_message)

@bot.command()
async def close(ctx, channel: disnake.TextChannel): #Команда close
    if ctx.author.id == int(channel.name.split('-')[1]) or ctx.author.guild_permissions.manage_channels:
        await channel.delete()
        await ctx.send(f'Тикет {channel.mention} закрыт.')
    else:
        await ctx.send("У вас нет прав на закрытие этого тикета.")

@close.error #Сообщения о том что у человека нет прав для исп. команнды close
async def close_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("У вас нет прав для закрытия тикетов.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Пожалуйста, укажите корректный канал.")

@status.error #Сообщения о том что у человека нет прав для исп. команнды status
async def status_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("У вас нет прав для просмотра тикетов.")

bot.run(settings['token'])
