import asyncio
from telethon import events
from telethon import TelegramClient
from telethon.tl.functions.messages import SendMediaRequest
from telethon.tl.types import InputMediaPhotoExternal, InputMediaDocumentExternal

API_ID = #твой ключ
API_HASH = 'твой ключ'
SESSION_NAME = 'session_name'

client = TelegramClient(SESSION_NAME, api_id=API_ID, api_hash=API_HASH)

async def main():
    await client.start()
    print('все! акк спиздил')

    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        if not event.is_private:
            return

        print(f'пиздит чет {event.sender_id}')

        text_answer = 'менеджер сноу джугает бабки и факает телочек'
        photo_url = 'https://i.ibb.co/Jj5QWSFZ/image.png'
        gif_url = 'https://s4.ezgif.com/tmp/ezgif-4efb6e1244423095.gif'

        try:
            await client(SendMediaRequest(
                peer=event.chat_id,
                media=InputMediaPhotoExternal(url=photo_url),
                message=text_answer
            ))
            print('нюдсы бля')
        except Exception as e:
            print(f'сука нет нюдсов: {e}')

        try:
            await client(SendMediaRequest(
                peer=event.chat_id,
                media=InputMediaDocumentExternal(url=gif_url),
                message=''
            ))
            print('домашнее порно!')
        except Exception as e:
            print(f'где порно суки: {e}')

    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
