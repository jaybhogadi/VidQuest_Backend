import websockets
import asyncio

async def test_websocket():
    uri = "wss://vidquest-backend.onrender.com/ws?requestId=12345&numMCQs=5"
    async with websockets.connect(uri) as websocket:
        await websocket.send("Hello, WebSocket!")
        response = await websocket.recv()
        print(f"Response: {response}")

asyncio.run(test_websocket())