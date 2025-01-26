import disnake
from disnake.ext import commands, tasks
from disnake.ui import Button, View, Select, Modal, TextInput
from disnake import File

from gtts import gTTS
import asyncio

from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji

import io
import requests
import datetime
from colorama import init, Fore
import time
import os
import sqlite3
from config import settings

intents = disnake.Intents.all()

bot = commands.Bot(command_prefix = settings['prefix'], intents = intents)
bot.remove_command('help')

connection = sqlite3.connect('server.db')
cursor = connection.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    message_content TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')

connection.commit()

# Словарь для хранения времени нахождения пользователя в голосовом чате
voice_time_tracking = {}
# Частота начислений в минутах
reward_interval_minutes = 5
# Награда за интервал (в листиках)
reward_per_interval = 10

TICKET_CHANNEL_ID = 1299473325327777802
VOICE_CHANNEL_ID = 1331730513563615322
ticket_admin_messages = {}
date = datetime.datetime.now().time()

last_ctx = None
last_message = None

init(autoreset=True)

class bcolors:
    HEADER = Fore.MAGENTA
    OKBLUE = Fore.BLUE
    OKCYAN = Fore.CYAN
    OKGREEN = Fore.GREEN
    WARNING = Fore.YELLOW
    FAIL = Fore.RED
    ENDC = Fore.RESET
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

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
    print()
    print('     ' + bcolors.OKCYAN + '=================================================' + bcolors.ENDC)
    print()
    print('     ' + bcolors.BOLD + 'Bot connected and voice reward system initialized' + bcolors.ENDC)
    print()
    print('     ' + bcolors.OKCYAN + '=================================================' + bcolors.ENDC)
    print()

    # Подключение к голосовому каналу
    guild = bot.get_guild(667378391229530123)  # ID сервера
    voice_channel = guild.get_channel(1331730513563615322)  # ID голосового канала

    if voice_channel:
        # Присоединение к голосовому каналу
        await voice_channel.connect()
        current_time = datetime.datetime.now()
        print()
        print(f"{bcolors.HEADER} >>> Бот подключился к каналу: \"{voice_channel.name}\"{bcolors.ENDC}")
        print()
    else:
        print("Не удалось найти голосовой канал")

    # Работа с тикет-каналом
    channel = bot.get_channel(TICKET_CHANNEL_ID)  #ID канала куда бот будет присылать кнопку для создания тикета
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
    await bot.change_presence(activity = disnake.Activity(name = f'!help', type = disnake.ActivityType.listening))

@bot.event
async def on_member_join(member):
    if cursor.execute(f"SELECT id FROM users WHERE id = {member.id}").fetchone() is None:
        cursor.execute(f"INSERT INTO users VALUES ('{member}',{member.id},0,0, {member.guild.id})")
        connection.commit()
    else:
        pass

@bot.event
async def on_message(message):
    # Проверяем, что сообщение пришло из нужного канала
    if message.channel.id == 667378391753949189:
        # Регистрируем сообщение пользователя в базе данных
        cursor.execute(f"INSERT INTO messages (user_id, message_content) VALUES (?, ?)",
                       (message.author.id, message.content))
        connection.commit()
    # Убедимся, что другие команды тоже обрабатываются
    await bot.process_commands(message)

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

# Создаем команду для просмотра баланса
@bot.command(aliases=['balance'])
async def __balance(ctx, member: disnake.Member = None):
    if member is None:
        member = ctx.author

    # Проверка на наличие аватара у пользователя
    if member.avatar is not None:
        avatar_bytes = await member.avatar.read()
        avatar_image = Image.open(io.BytesIO(avatar_bytes))
        avatar_image = avatar_image.resize((100, 100))

        # Создаем маску для круглой аватарки
        mask = Image.new("L", (100, 100), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.ellipse((0, 0, 100, 100), fill=255)
        avatar_image = avatar_image.convert("RGBA")
        avatar_image.putalpha(mask)
    else:
        # Загрузка стандартного изображения, если аватара нет
        avatar_image = Image.new("RGBA", (100, 100), (100, 100, 100, 255))
        draw = ImageDraw.Draw(avatar_image)
        draw.text((10, 40), "No Avatar", fill=(255, 255, 255))

    user_balance = cursor.execute("SELECT cash FROM users WHERE id = ?", (member.id,)).fetchone()[0]
    user_name = str(member)

    background_image = Image.open("balance.jpg")
    background_image = background_image.resize((400, 200))
    img = background_image
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype('arial.ttf', 20)
    except IOError:
        font = ImageFont.load_default()

    img.paste(avatar_image, (20, 55), avatar_image)

    text_balance = f"{user_balance} 🍃"
    text_user = f"{user_name}"

    # Получаем размеры текста для правильного выравнивания
    text_user_width, text_user_height = draw.textbbox((0, 0), text_user, font=font)[2:4]
    text_balance_width, text_balance_height = draw.textbbox((0, 0), text_balance, font=font)[2:4]

    user_x = (img.width - text_user_width) // 2 + 50
    balance_x = (img.width - text_balance_width) // 2 + 72

    with Pilmoji(img) as pilmoji:
        pilmoji.text((user_x, 55), text_user, fill=(30, 30, 30), font=font)
        pilmoji.text((balance_x, 130), text_balance, fill=(30, 30, 30), font=font)

    # Сохраняем изображение в байтовый поток
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    button_shop = Button(label="Открыть магазин", style=disnake.ButtonStyle.green)
    button_transfer = Button(label="Перевод", style=disnake.ButtonStyle.blurple)

    # Обработчик кнопки "Открыть магазин"
    def create_button_shop_callback(author_id):
        async def button_shop_callback(interaction: disnake.MessageInteraction):
            if interaction.user.id != author_id:
                await interaction.response.send_message("Вы не можете использовать эту кнопку.", ephemeral=True)
                return
            await show_shop(interaction)
        return button_shop_callback

    # Обработчик кнопки "Перевод"
    def create_button_transfer_callback(author_id):
        async def button_transfer_callback(interaction: disnake.MessageInteraction):
            if interaction.user.id != author_id:
                await interaction.response.send_message("Вы не можете использовать эту кнопку.", ephemeral=True)
                return
            # Удаляем сообщение с изображением и кнопками
            await interaction.message.delete()
            # Открываем меню перевода
            await open_transfer_menu(interaction)
        return button_transfer_callback

    button_shop.callback = create_button_shop_callback(ctx.author.id)
    button_transfer.callback = create_button_transfer_callback(ctx.author.id)

    # Добавляем кнопки в представление и отправляем изображение
    view = View()
    view.add_item(button_shop)
    view.add_item(button_transfer)
    await ctx.send(file=disnake.File(buffer, "balance.png"), view=view)

# Функция для открытия меню перевода
async def open_transfer_menu(interaction):
    author_id = interaction.user.id  # Сохраняем ID автора

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
        options=[disnake.SelectOption(label=member.display_name, value=str(member.id))
                 for member in members]
    )

    async def select_callback(interaction: disnake.MessageInteraction):
        # Проверяем, что взаимодействует только автор команды
        if interaction.user.id != author_id:
            await interaction.response.send_message("Вы не можете использовать это меню.", ephemeral=True)
            return

        selected_user_id = int(select_menu.values[0])
        await interaction.message.delete()
        await request_transfer_amount(interaction, selected_user_id)

    select_menu.callback = select_callback

    view = View()
    view.add_item(select_menu)
    await interaction.response.send_message("Выберите пользователя для перевода:", view=view)

# Функция для запроса суммы перевода
async def request_transfer_amount(interaction: disnake.MessageInteraction, selected_user_id: int):
    # Создаем модальное окно для ввода суммы
    class TransferModal(disnake.ui.Modal):
        def __init__(self):
            amount_input = disnake.ui.TextInput(
                label="Сумма", 
                placeholder="Введите сумму", 
                required=True, 
                max_length=10, 
                custom_id="transfer_amount_input"
            )
            super().__init__(title="Введите сумму перевода", components=[amount_input])
            self.amount_input = amount_input

        async def callback(self, interaction: disnake.MessageInteraction):
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
async def show_shop(interaction: disnake.MessageInteraction):
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

@bot.command(aliases=["profile"])
async def user_profile(ctx, member: disnake.Member = None):
    if member is None:
        member = ctx.author

    # Получаем баланс и количество сообщений
    user_balance = cursor.execute("SELECT cash FROM users WHERE id = ?", (member.id,)).fetchone()[0]
    message_count = cursor.execute("SELECT COUNT(*) FROM messages WHERE user_id = ?", (member.id,)).fetchone()[0]

    # Получаем аватар пользователя
    avatar_bytes = await member.avatar.read()
    avatar_image = Image.open(io.BytesIO(avatar_bytes))
    avatar_image = avatar_image.resize((100, 100))

    place = cursor.execute("SELECT COUNT(*) FROM users WHERE cash > ? AND server_id = ?", (user_balance, ctx.guild.id)).fetchone()[0] + 1

    # Получаем роли пользователя
    roles = [role.mention for role in member.roles if role != ctx.guild.default_role]  # Исключаем @everyone роль

    # Если у пользователя нет ролей, выводим сообщение
    roles_string = ", ".join(roles) if roles else "Нет ролей"

    # Создаем Embed с профилем
    embed = disnake.Embed(title=f"Профиль: ***{member.display_name}***", description=f"Баланс: {user_balance} 🍃")
    embed.add_field(name="Сообщений отправлено", value=str(message_count), inline=False)
    embed.add_field(name="Место в лидерборде", value=f"#{place}", inline=False)
    embed.add_field(name="Роли:", value=roles_string, inline=False)
    
    # Вставляем аватарку
    avatar_url = member.avatar.url
    embed.set_thumbnail(url=avatar_url)

    # Отправляем Embed
    msg = await ctx.send(embed=embed)

@bot.command(pass_context=True)
async def help(ctx):
    emb = disnake.Embed(title='**Навигация по командам сервера** :leaves:', color=0x95a5a6)
    emb.set_author(name=bot.user.name, icon_url=bot.user.avatar)

    emb.add_field(name='**!balance**', value='Проверить баланс любого пользователя')
    emb.add_field(name='**!award**', value='Выдать награждение пользователю')
    emb.add_field(name='**!deprive**', value='Отобрать любое количество валюты') 
    emb.add_field(name='**!leaderboard**', value='Посмотреть топ 10 сервера по балансу')
    emb.add_field(name='**Ticket**', value='Вы так же можете открыть тикет в чате <#1299473325327777802>')
    emb.add_field(name='**!profile**', value='Посмотерть профиль пользователя')
    emb.set_footer(text="мяу")

    message = await ctx.send(embed=emb)

    # Добавляем реакции флагов
    await message.add_reaction('🇺🇸')  # Флаг США
    await message.add_reaction('🇷🇺')  # Флаг России

    # Сохраняем ID сообщения и пользователя для проверки
    bot.help_message_id = message.id
    bot.help_user_id = ctx.author.id

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:  # Игнорируем реакции от ботов
        return

    if reaction.emoji == '🇺🇸':
        # Переводим на английский
        emb = disnake.Embed(title='**Server Command Navigation** :leaves:', color=0x95a5a6)
        emb.set_author(name=bot.user.name, icon_url=bot.user.avatar)

        emb.add_field(name='**!balance**', value='Check any user\'s balance')
        emb.add_field(name='**!award**', value='Give an award to a user')
        emb.add_field(name='**!deprive**', value='Revoke any amount of currency')
        emb.add_field(name='**!leaderboard**', value='View the top 10 server balances')
        emb.add_field(name='**Ticket**', value='You can also open a ticket in the chat <#1299473325327777802>')
        emb.add_field(name='**!profile**', value='Check profile')
    
        emb.set_footer(text="meow")

        # Обновляем сообщение
        await reaction.message.edit(embed=emb)
        await reaction.remove(user)

    elif reaction.emoji == '🇷🇺':
        # Переводим на русский
        emb = disnake.Embed(title='**Навигация по командам сервера** :leaves:', color=0x95a5a6)
        emb.set_author(name=bot.user.name, icon_url=bot.user.avatar)

        emb.add_field(name='**!balance**', value='Проверить баланс любого пользователя')
        emb.add_field(name='**!award**', value='Выдать награждение пользователю')
        emb.add_field(name='**!deprive**', value='Отобрать любое количество валюты') 
        emb.add_field(name='**!leaderboard**', value='Посмотреть топ 10 сервера по балансу')
        emb.add_field(name='**Ticket**', value='Вы так же можете открыть тикет в чате <#1299473325327777802>')
        emb.add_field(name='**!profile**', value='Посмотерть профиль пользователя')
        emb.set_footer(text="мяу")

        # Обновляем сообщение
        await reaction.message.edit(embed=emb)
        await reaction.remove(user)

roles_shop = {
    "сок-rich": {"cost": 1000, "role_id": 1300142132576784506},
    "пикми": {"cost": 10000, "role_id": 1332767211219189770} 
}


@bot.slash_command(name="shop", description="Показать доступные роли для покупки")
async def shop(interaction: disnake.ApplicationCommandInteraction):
    await interaction.response.defer()  # Откладываем ответ

    # Создаем Embed с ролями
    embed = disnake.Embed(title="Магазин ролей", description="Доступные роли для покупки")

    embed.set_thumbnail(url="attachment://icon.gif")

    # Добавляем роли
    for role_name, role_info in roles_shop.items():
        embed.add_field(
            name=role_name,
            value=f"Цена: {role_info['cost']} :leaves:",
            inline=False
        )
    
    # Локальные файлы
    icon_file = File("icon.gif", filename="icon.gif")   # Локальная GIF-иконка

    # Отправляем файл и Embed в одном сообщении
    await interaction.edit_original_response(
        files=[icon_file],  # Локальные файлы
        embed=embed                    # Embed с ролями
    )

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
    current_time = datetime.datetime.now()
    global last_message
    if last_message:
        print(f"[{current_time}] Обновляем кнопку в сообщении")
        new_view = create_ticket_view()
        await last_message.edit(view=new_view)  # Обновляем только кнопку

@bot.event
async def on_interaction(interaction):
    if interaction.type == disnake.InteractionType.application_command:
        return #если команда слеш то проверку не делаем в наш случае для команды /status
    try:
        # Closing the ticket
        if interaction.data['custom_id'].startswith('close_ticket-'):
            user_id = interaction.data['custom_id'].split('-')[1]
            
            if (interaction.user.id == int(user_id) or disnake.utils.get(interaction.user.roles, id=1300843105532117002) or interaction.user.guild_permissions.administrator):
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

@bot.slash_command(name="status", description="Показать открытые тикеты")
@commands.has_permissions(manage_channels=True)
async def status(interaction: disnake.AppCmdInter):
    open_tickets = [channel for channel in interaction.guild.channels if channel.name.startswith('ticket-')]

    if not open_tickets:
        await interaction.response.send_message("Нет открытых тикетов.")
        return

    status_message = "Открытые тикеты:\n" + "\n".join([f"{channel.mention} - {channel.name}" for channel in open_tickets])
    await interaction.response.send_message(status_message)

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

@bot.command()
async def connect(ctx):
    #Перемещает бота в голосовой канал, где находится вызывающий пользователь.
    if ctx.author.voice:
        current_vc = ctx.voice_client
        if current_vc:
            await current_vc.move_to(ctx.author.voice.channel)
        else:
            channel_to_join = ctx.author.voice.channel
            await channel_to_join.connect()
            await ctx.send(f"Я подключился к вашему каналу: {channel_to_join.name}.")
    else:
        await ctx.send("Вы не находитесь в голосовом канале.")

@bot.command()
async def disconnect(ctx):
    #Отключает бота от текущего голосового канала и возвращает его в изначальный.
    if ctx.voice_client:
        initial_channel = bot.get_channel(VOICE_CHANNEL_ID)
        await ctx.voice_client.disconnect()
        await initial_channel.connect()
    else:
        await ctx.send("Я не в голосовом канале.")

@bot.command()
async def say(ctx, *, text: str):
    if ctx.voice_client:
        # Создаем аудиофайл с помощью gTTS
        tts = gTTS(text=text, lang='ru')
        tts.save("temp_audio.mp3")

        # Отправляем аудиофайл в голосовой канал
        ctx.voice_client.play(disnake.FFmpegPCMAudio("temp_audio.mp3"))

        # Удаляем временный файл после воспроизведения
        while ctx.voice_client.is_playing():
            await asyncio.sleep(1)
        os.remove("temp_audio.mp3")
    else:
        await ctx.send("Я не подключен к голосовому каналу.")

@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel is not None and before.channel is None:  # Пользователь подключился
        if member.bot:  # Игнорируем, если это бот
            return

        # Получите голосовой канал, в который подключился пользователь
        voice_client = disnake.utils.get(bot.voice_clients, guild=member.guild)
        if voice_client is not None:
            # Задержка на 1 секунду перед воспроизведением
            await asyncio.sleep(1)

            # Создаем аудиофайл с помощью gTTS
            display_name = member.display_name  # Имя пользователя на сервере
            text = f"Здравствуйте {display_name}, сосите!"
            tts = gTTS(text=text, lang='ru')
            tts.save("temp_audio.mp3")

            # Воспроизводим аудиофайл
            voice_client.play(disnake.FFmpegPCMAudio("temp_audio.mp3"))

            # Ждем, пока аудио закончится воспроизводиться
            while voice_client.is_playing():
                await asyncio.sleep(1)

            # Удаляем временный файл после воспроизведения
            os.remove("temp_audio.mp3")

@bot.event
async def on_command_error(ctx, error):
    await ctx.send(f'Произошла ошибка: {error}')

bot.run(settings['token'])
