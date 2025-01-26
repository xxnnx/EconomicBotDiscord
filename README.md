# Банкирный крот ( Economic Discord Bot )

### Я создал экономического бота, с помощью которого вы можете отслеживать переводы, открывать баланс, использовать магазин и передовать вашу валюту между пользователями. Так же за то что пользователь сидит в войс чате, будет награда (она настраиваете в коде бота)

Чтобы использовать бота нужно загрузить библиотеки. И сам язык на котором написан бот.

1. Скачать python последней версии
2. Установить библиотеки:

   ```
    pip install PyNaCl
   ```
   ```
    pip install pynacl pyaudio speechrecognition
   ```
   ```
    pip install dysnake
   ```
   ```
    pip install pilmoji
   ```
   ```
    pip install colorama
   ```
   ```
    pip install numpy
   ```
   ```
    pip install disnake SpeechRecognition pyaudio
   ```
   ```
    pip install gTTS
   ```


### Если сделали все удачно, в терминале (start.bat) будет сообщение
![image](https://github.com/user-attachments/assets/49b8563f-bed0-45fc-a94c-1ed3097f0715)


> [!TIP]
> Для того, чтобы бот отправлял открытые тикеты в чат тикетов (канал где будут все тикеты, "для админов"), вам нужно создать чат и ввести идентификатор канала в код бота

> [!TIP]
> Чтобы создать новую базу данных. Просто удалите мою. Запускаем бота через "start.bat" :shipit:

> [!NOTE]
> Что нового в обновлении 1.0.0v
> Бот автоматически присоединяется в канал, с помощью команд его можно подключить в войс чат в котором находится человек вызывающий эту команду, с помощью бота можно воспроизводить сообщения, и привествие людей которые зашли в войс чат.

## Команды которые поддерживает бот:
!help - _Помощь по боту_

!award <user_nick> <amount> - _Выдать пользователю валюту_

!deprive <user_nick> <amount> - _Забрать валюту у пользователя_

!balance - _Посмотреть свой баланс_

!balance <user_nick> - _Посмотреть баланс пользователя_

!leaderboard - _Посмотерть топ 10 сервера по балансу_

!shop - _Открыть магазин-ролей_

!buy <name_role> - _Купить роль на сервере_

!profile - Посмотерть профиль пользователя

!connect - _Подключение к войс чату_

!disconnect - _Отключение от войс чата и переход в комнату ожидания_

!say <сообещние> - _Воспроизведение сообщения от лица бота_

### ___Для админов:___
!ticket - _Нужна для создания сообщения, через которое человек может создать тикет_
![image](https://github.com/user-attachments/assets/a117696e-67e8-4250-92aa-e8f9f9c9796b)

!close <#ID Channel> - _Нужна чтобы принудительно закрыть тикет, но у админа и у человека который создал тикет есть кнопка Закрытия тикета_

!status - _Посмотреть открытые тикеты_
