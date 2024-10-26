import disnake
from disnake.ext import commands
import datetime
import os

import sqlite3
from config import settings

intents = disnake.Intents.all()

bot = commands.Bot(command_prefix = settings['prefix'], intents = intents)
bot.remove_command('help')

connection = sqlite3.connect('server.db')
cursor = connection.cursor()

TICKET_CHANNEL_ID = 1299473325327777802
ROLE_ID = 1261062562833764362

@bot.event
async def on_ready():

    channel = bot.get_channel(1299473325327777802)
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
    await bot.change_presence(status = disnake.Status.dnd, activity = disnake.Activity(name = f'!help 👨‍⚖️', type = disnake.ActivityType.playing))
    print('Bot connected')

@bot.event
async def on_member_join(member):
    if cursor.execute(f"SELECT id FROM users WHERE id = {member.id}").fetchone() is None:
        cursor.execute(f"INSERT INTO users VALUES ('{member}',{member.id},0,0, {member.guild.id})")
        connection.commit()
    else:
        pass

if not os.path.exists('ticket_log.txt'):
    with open('ticket_log.txt', 'w') as log_file:
        log_file.write("Лог тикетов:\n")

def log_to_file(log_message):
    with open('ticket_log.txt', 'a') as log_file:
        log_file.write(f"{datetime.datetime.now()}: {log_message}\n")

@bot.command(aliases = ['balance'])
async def __balance(ctx, member: disnake.Member = None):
    if member is None:
        await ctx.send(embed = disnake.Embed(
            description = f"""Баланс пользователя **{ctx.author}** 

            :leaves: **{cursor.execute("SELECT cash FROM users WHERE id = {}".format(ctx.author.id)).fetchone()[0]} :leaves:**"""
        ))
    else:
        await ctx.send(embed = disnake.Embed(
            description = f"""Баланс пользователя **{member}:** 

            :leaves: **{cursor.execute("SELECT cash FROM users WHERE id = {}".format(member.id)).fetchone()[0]} :leaves:**"""
        ))

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

class MyModal(disnake.ui.Modal):
    def __init__(self):
        # компонтеты окна
        components = [
            disnake.ui.TextInput(
                label="Ваш ник",
                placeholder="Введите ваш ник",
                custom_id="nickname",
                style=disnake.TextInputStyle.short,
                max_length=50,
            ),
            disnake.ui.TextInput(
                label="Описание",
                placeholder="Введите описание проблемы.",
                custom_id="description",
                style=disnake.TextInputStyle.paragraph,
            ),
        ]
        super().__init__(
            title="Создание тикета",
            custom_id="create_ticket_modal",
            components=components,
        )

    async def callback(self, inter: disnake.ModalInteraction): #обработка ответа идет
        nickname = inter.text_values["nickname"]
        description = inter.text_values["description"]
        
        guild = inter.guild  # Получаем гильдию из взаимодействия
        
        overwrites = {
            guild.default_role: disnake.PermissionOverwrite(read_messages=False),
            inter.user: disnake.PermissionOverwrite(read_messages=True)
        }

        channel = await guild.create_text_channel(f'ticket-{inter.user.id}', overwrites=overwrites)

        embed = disnake.Embed(title="Новый тикет", description=description, color=disnake.Color.blue())
        embed.add_field(name="Ник", value=nickname)
        embed.add_field(name="Создан пользователем", value=inter.user.mention)

        await channel.send(embed=embed)

        await channel.send(f'Привет {inter.user.mention}, чем мы можем помочь?')
        # кнопка закрытия тикета
        close_button = disnake.ui.Button(label="Закрыть тикет", style=disnake.ButtonStyle.red, custom_id=f'close_ticket-{inter.user.id}')
        close_view = disnake.ui.View()
        close_view.add_item(close_button)

        await channel.send("Нажмите кнопку ниже, чтобы закрыть тикет:", view=close_view)
        await inter.response.send_message(f'Тикет создан: {channel.mention}', ephemeral=True)

@bot.command()
async def ticket(ctx):
    user_tickets = [channel for channel in ctx.guild.channels if channel.name.startswith(f'ticket-{ctx.author.id}-')]

    if user_tickets:
        await ctx.send("Вы уже открыли тикет. Пожалуйста, закройте его перед созданием нового.")
        return

    button = disnake.ui.Button(label="Создать тикет", style=disnake.ButtonStyle.primary, custom_id="create_ticket")
    view = disnake.ui.View()
    view.add_item(button)

    await ctx.send("Нажмите кнопку ниже для создания тикета:", view=view)

    async def button_callback(interaction):
        modal = MyModal()  # Используем ваш класс MyModal
        await interaction.response.send_modal(modal)

    button.callback = button_callback

@bot.event
async def on_interaction(interaction):
    if interaction.data['custom_id'].startswith('close_ticket-'):
        user_id = interaction.data['custom_id'].split('-')[1]
        
        if interaction.user.id == int(user_id) or interaction.user.guild_permissions.manage_channels:
            channel = interaction.channel
            await interaction.response.send_message(f'Тикет {channel.mention} закрыт.', ephemeral=True)
            await channel.delete()
            log_to_file(f"Тикет закрыт: {channel.name} пользователем {interaction.user.name}")
        else:
            await interaction.response.send_message("У вас нет прав на закрытие этого тикета.", ephemeral=True)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def status(ctx):
    open_tickets = [channel for channel in ctx.guild.channels if channel.name.startswith('ticket-')]
    
    if not open_tickets:
        await ctx.send("Нет открытых тикетов.")
        return

    status_message = "Открытые тикеты:\n" + "\n".join([f"{channel.mention} - {channel.name}" for channel in open_tickets])
    await ctx.send(status_message)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.name.startswith('ticket-'):
        admin_channel = disnake.utils.get(message.guild.channels, name='admin-channel')
        if admin_channel:
            await admin_channel.send(f'Тикет от {message.author.mention} в канале {message.channel.mention}: {message.content}')
            log_to_file(f"Сообщение от {message.author.name} в {message.channel.name}: {message.content}")

    await bot.process_commands(message)

@bot.command()
async def close(ctx, channel: disnake.TextChannel):
    if ctx.author.id == int(channel.name.split('-')[1]) or ctx.author.guild_permissions.manage_channels:
        await channel.delete()
        await ctx.send(f'Тикет {channel.mention} закрыт.')
        log_to_file(f"Тикет закрыт: {channel.name} пользователем {ctx.author.name}")
    else:
        await ctx.send("У вас нет прав на закрытие этого тикета.")

@close.error
async def close_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("У вас нет прав для закрытия тикетов.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Пожалуйста, укажите корректный канал.")


@status.error
async def status_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("У вас нет прав для просмотра тикетов.")

bot.run(settings['token'])
