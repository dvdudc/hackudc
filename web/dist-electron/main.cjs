"use strict";
var _documentCurrentScript = typeof document !== "undefined" ? document.currentScript : null;
const { app, BrowserWindow, ipcMain, screen } = require("electron");
const path = require("path");
const { fileURLToPath } = require("url");
const __dirname$1 = path.dirname(__filename || fileURLToPath(typeof document === "undefined" ? require("url").pathToFileURL(__filename).href : _documentCurrentScript && _documentCurrentScript.tagName.toUpperCase() === "SCRIPT" && _documentCurrentScript.src || new URL("main.cjs", document.baseURI).href));
process.env.DIST = path.join(__dirname$1, "../dist");
process.env.VITE_PUBLIC = app.isPackaged ? process.env.DIST : path.join(process.env.DIST, "../public");
let win;
const VITE_DEV_SERVER_URL = process.env["VITE_DEV_SERVER_URL"];
const WIDGET_SIZE = 250;
function createWindow() {
  const primaryDisplay = screen.getPrimaryDisplay();
  const { width, height } = primaryDisplay.workAreaSize;
  const vitePublic = process.env.VITE_PUBLIC || "";
  win = new BrowserWindow({
    icon: path.join(vitePublic, "electron-vite.svg"),
    webPreferences: {
      preload: path.join(__dirname$1, "preload.mjs"),
      nodeIntegration: true,
      contextIsolation: true
    },
    // Frameless, transparent widget params
    width: WIDGET_SIZE,
    height: WIDGET_SIZE,
    x: width - WIDGET_SIZE - 20,
    // Bottom right
    y: height - WIDGET_SIZE - 20,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false
    // Widget starts fixed size
  });
  win.webContents.on("did-finish-load", () => {
    win?.webContents.send("main-process-message", (/* @__PURE__ */ new Date()).toLocaleString());
  });
  if (VITE_DEV_SERVER_URL) {
    win.loadURL(VITE_DEV_SERVER_URL);
  } else {
    win.loadFile(path.join(process.env.DIST || "", "index.html"));
  }
}
ipcMain.on("window-expand", () => {
  if (win) {
    const primaryDisplay = screen.getPrimaryDisplay();
    const { width, height } = primaryDisplay.workAreaSize;
    win.setBounds({ x: 0, y: 0, width, height }, true);
    win.setResizable(true);
    win.setAlwaysOnTop(false);
  }
});
ipcMain.on("window-shrink", () => {
  if (win) {
    const primaryDisplay = screen.getPrimaryDisplay();
    const { width, height } = primaryDisplay.workAreaSize;
    win.setBounds({
      x: width - WIDGET_SIZE - 20,
      y: height - WIDGET_SIZE - 20,
      width: WIDGET_SIZE,
      height: WIDGET_SIZE
    }, true);
    win.setResizable(false);
    win.setAlwaysOnTop(true);
  }
});
ipcMain.on("window-close", () => {
  app.quit();
});
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
    win = null;
  }
});
app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
app.whenReady().then(createWindow);
