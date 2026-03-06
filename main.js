const { app, BrowserWindow, nativeTheme } = require('electron');
const path = require('path');

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
