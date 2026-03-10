const { app, BrowserWindow, nativeTheme, ipcMain } = require('electron');
const path = require('path');
const sqlite3 = require('sqlite3').verbose();

const dbPath = path.join(__dirname, 'erp_nicoletti.db');
const db = new sqlite3.Database(dbPath, (err) => {
    if (err) console.error('Error opening database', err);
});

// Setup DB
db.serialize(() => {
    db.run(`CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY,
        entity TEXT,
        account TEXT,
        category TEXT,
        type TEXT,
        amount REAL,
        desc TEXT,
        date TEXT,
        groupId INTEGER,
        currency TEXT DEFAULT 'ARS'
    )`);

    // Intentar agregar la columna por si la tabla ya existía
    db.run(`ALTER TABLE transactions ADD COLUMN currency TEXT DEFAULT 'ARS'`, (err) => {
        // Ignorar el error si la columna ya existe
    });
});

// IPC CRUD
ipcMain.handle('get-transactions', () => {
    return new Promise((resolve, reject) => {
        db.all("SELECT * FROM transactions ORDER BY id DESC", [], (err, rows) => {
            if (err) reject(err);
            resolve(rows);
        });
    });
});

ipcMain.handle('add-transaction', (event, tx) => {
    return new Promise((resolve, reject) => {
        const stmt = db.prepare("INSERT INTO transactions (id, entity, account, category, type, amount, desc, date, groupId, currency) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)");
        stmt.run(tx.id, tx.entity, tx.account, tx.category, tx.type, tx.amount, tx.desc, tx.date, tx.groupId || null, tx.currency || 'ARS', function (err) {
            if (err) reject(err);
            resolve(this.lastID);
        });
        stmt.finalize();
    });
});

ipcMain.handle('delete-transaction', (event, id, groupId) => {
    return new Promise((resolve, reject) => {
        if (groupId) {
            db.run("DELETE FROM transactions WHERE groupId = ?", [groupId], function (err) {
                if (err) reject(err);
                resolve(this.changes);
            });
        } else {
            db.run("DELETE FROM transactions WHERE id = ?", [id], function (err) {
                if (err) reject(err);
                resolve(this.changes);
            });
        }
    });
});

function createWindow() {
    const win = new BrowserWindow({
        width: 1400,
        height: 900,
        minWidth: 1024,
        minHeight: 768,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false
        },
        backgroundColor: '#f8fafc',
        show: false, // Ocultar hasta que esté lista para dar un efecto cinemático
        titleBarStyle: 'hidden',
        titleBarOverlay: {
            color: '#f8fafc',
            symbolColor: '#0f172a',
            height: 40
        }
    });

    win.loadFile('index.html');

    // Maximizar y mostrar la app cuando ya haya renderizado el HTML
    win.once('ready-to-show', () => {
        win.show();
        win.maximize();
    });
}

app.whenReady().then(() => {
    nativeTheme.themeSource = 'light';
    createWindow();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});
