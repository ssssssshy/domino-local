let ws = null;
let playerNum = null;
let gameState = {
    hand: [],
    board: [],
    yourTurn: false
};

function generateRoomId() {
    return 'room_' + Math.random().toString(36).substr(2, 9);
}

function connectToRoom(roomId) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${window.location.host}/ws/${roomId}`;
    
    ws = new WebSocket(url);
    
    ws.onopen = function() {
        console.log('Connected to room:', roomId);
        document.getElementById('room-input').style.display = 'none';
        document.getElementById('connect-btn').style.display = 'none';
        document.getElementById('create-btn').style.display = 'none';
        document.getElementById('room-id-display').textContent = `Room ID: ${roomId}`;
        document.getElementById('status').textContent = 'Waiting for opponent...';
    };
    
    ws.onmessage = function(event) {
        const msg = JSON.parse(event.data);
        handleMessage(msg);
    };
    
    ws.onerror = function(error) {
        console.error('WebSocket error:', error);
        document.getElementById('status').textContent = 'Connection error!';
    };
    
    ws.onclose = function() {
        console.log('Disconnected from server');
        document.getElementById('status').textContent = 'Disconnected!';
    };
}

function handleMessage(msg) {
    if (msg.type === 'init') {
        console.log('Game initialized');
        gameState.hand = msg.hand;
        gameState.board = msg.board;
        gameState.yourTurn = msg.your_turn;
        document.getElementById('status').textContent = 'Game started!';
        render();
    } else if (msg.type === 'update') {
        gameState.hand = msg.hand;
        gameState.board = msg.board;
        gameState.yourTurn = msg.your_turn;
        render();
    } else if (msg.type === 'msg') {
        console.log('Message:', msg.text);
        showNotification(msg.text);
    }
}

function showNotification(text) {
    const notification = document.getElementById('notification');
    notification.textContent = text;
    notification.style.display = 'block';
    setTimeout(() => {
        notification.style.display = 'none';
    }, 5000);
}

function playTile(index) {
    if (!gameState.yourTurn) {
        showNotification('Not your turn!');
        return;
    }
    
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            action: 'play',
            index: index
        }));
    }
}

function render() {
    const container = document.getElementById('game-table');
    container.innerHTML = '';
    
    // Status
    const status = document.getElementById('status');
    if (gameState.yourTurn) {
        status.textContent = 'Your turn!';
        status.style.color = '#00cc00';
    } else {
        status.textContent = 'Opponent\'s turn...';
        status.style.color = '#ff6666';
    }
    
    // Board
    const boardDiv = document.createElement('div');
    boardDiv.className = 'board';
    boardDiv.innerHTML = '<h3>Board:</h3>';
    
    if (gameState.board.length === 0) {
        boardDiv.innerHTML += '<p style="color: #999;">Board is empty...</p>';
    } else {
        const boardTiles = document.createElement('div');
        boardTiles.className = 'board-tiles';
        gameState.board.forEach((tile, idx) => {
            const tileDiv = document.createElement('div');
            tileDiv.className = 'tile board-tile';
            tileDiv.innerHTML = `<span>${tile[0]}</span><span>|</span><span>${tile[1]}</span>`;
            boardTiles.appendChild(tileDiv);
        });
        boardDiv.appendChild(boardTiles);
    }
    
    container.appendChild(boardDiv);
    
    // Hand
    const handDiv = document.createElement('div');
    handDiv.className = 'hand-section';
    handDiv.innerHTML = `<h3>Your hand (${gameState.hand.length} tiles):</h3>`;
    
    const handTiles = document.createElement('div');
    handTiles.className = 'hand-tiles';
    gameState.hand.forEach((tile, idx) => {
        const tileDiv = document.createElement('div');
        tileDiv.className = 'tile hand-tile';
        tileDiv.innerHTML = `<span>${tile[0]}</span><span>|</span><span>${tile[1]}</span>`;
        tileDiv.onclick = () => {
            if (gameState.yourTurn) {
                playTile(idx);
            }
        };
        
        if (gameState.yourTurn) {
            tileDiv.style.cursor = 'pointer';
            tileDiv.onmouseover = () => tileDiv.style.transform = 'translateY(-10px)';
            tileDiv.onmouseout = () => tileDiv.style.transform = 'translateY(0)';
        }
        
        handTiles.appendChild(tileDiv);
    });
    
    handDiv.appendChild(handTiles);
    container.appendChild(handDiv);
}

window.addEventListener('load', function() {
    const roomInput = document.getElementById('room-input');
    const connectBtn = document.getElementById('connect-btn');
    const createBtn = document.getElementById('create-btn');
    
    connectBtn.addEventListener('click', function() {
        const roomId = roomInput.value.trim();
        if (roomId) {
            connectToRoom(roomId);
        } else {
            alert('Please enter a room ID');
        }
    });
    
    createBtn.addEventListener('click', function() {
        const roomId = generateRoomId();
        roomInput.value = roomId;
        connectToRoom(roomId);
    });
    
    roomInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            connectBtn.click();
        }
    });
});
