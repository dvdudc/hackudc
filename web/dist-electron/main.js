"use strict";
Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
const electron = require("electron");
const path = require("node:path");
const node_url = require("node:url");
const node_child_process = require("node:child_process");
var _documentCurrentScript = typeof document !== "undefined" ? document.currentScript : null;
const __dirname$1 = path.dirname(node_url.fileURLToPath(typeof document === "undefined" ? require("url").pathToFileURL(__filename).href : _documentCurrentScript && _documentCurrentScript.tagName.toUpperCase() === "SCRIPT" && _documentCurrentScript.src || new URL("main.js", document.baseURI).href));
process.env.APP_ROOT = path.join(__dirname$1, "..");
const VITE_DEV_SERVER_URL = process.env["VITE_DEV_SERVER_URL"];
const MAIN_DIST = path.join(process.env.APP_ROOT, "dist-electron");
const RENDERER_DIST = path.join(process.env.APP_ROOT, "dist");
process.env.VITE_PUBLIC = VITE_DEV_SERVER_URL ? path.join(process.env.APP_ROOT, "public") : RENDERER_DIST;
let win = null;
let apiProcess = null;
const WIDGET_SIZE = 140;
function startBackendApi() {
  const appRoot = process.env.APP_ROOT;
  const apiPath = path.join(appRoot, "..", "src", "api.py");
  console.log("Starting Python backend at:", apiPath);
  const pythonExecutable = process.platform === "win32" ? path.join(appRoot, "..", ".venv", "Scripts", "python.exe") : path.join(appRoot, "..", ".venv", "bin", "python");
  apiProcess = node_child_process.spawn(pythonExecutable, [apiPath], {
    cwd: path.join(appRoot, "..")
  });
  apiProcess.stdout?.on("data", (data) => {
    console.log(`API: ${data}`);
  });
  apiProcess.stderr?.on("data", (data) => {
    console.error(`API Error: ${data}`);
  });
}
function createWindow() {
  const primaryDisplay = electron.screen.getPrimaryDisplay();
  const { width, height } = primaryDisplay.workAreaSize;
  win = new electron.BrowserWindow({
    icon: path.join(process.env.VITE_PUBLIC || "", "electron-vite.svg"),
    webPreferences: {
      preload: path.join(__dirname$1, "preload.js"),
      nodeIntegration: true,
      contextIsolation: true
      // Required for secure IPC preload bridge
    },
    width: WIDGET_SIZE,
    height: WIDGET_SIZE,
    x: width - WIDGET_SIZE - 20,
    // pinned to right
    y: height - WIDGET_SIZE - 20,
    // pinned to bottom
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false
  });
  win.webContents.on("did-finish-load", () => {
    win?.webContents.send("main-process-message", (/* @__PURE__ */ new Date()).toLocaleString());
  });
  win.setIgnoreMouseEvents(false);
  if (VITE_DEV_SERVER_URL) {
    win.loadURL(VITE_DEV_SERVER_URL);
  } else {
    win.loadFile(path.join(RENDERER_DIST, "index.html"));
  }
}
electron.ipcMain.on("window-expand", () => {
  if (win) {
    const primaryDisplay = electron.screen.getPrimaryDisplay();
    const { width: screenWidth, height: screenHeight } = primaryDisplay.workAreaSize;
    const expandedWidth = 800;
    const expandedHeight = 600;
    win.setResizable(true);
    win.setBounds({
      x: screenWidth - expandedWidth - 20,
      y: screenHeight - expandedHeight - 20,
      width: expandedWidth,
      height: expandedHeight
    }, true);
  }
});
electron.ipcMain.on("window-shrink", () => {
  if (win) {
    const primaryDisplay = electron.screen.getPrimaryDisplay();
    const { width: screenWidth, height: screenHeight } = primaryDisplay.workAreaSize;
    win.setBounds({
      x: screenWidth - WIDGET_SIZE - 20,
      y: screenHeight - WIDGET_SIZE - 20,
      width: WIDGET_SIZE,
      height: WIDGET_SIZE
    }, true);
    win.setResizable(false);
  }
});
electron.ipcMain.on("window-expand-input", () => {
  if (win) {
    const primaryDisplay = electron.screen.getPrimaryDisplay();
    const { width: screenWidth, height: screenHeight } = primaryDisplay.workAreaSize;
    const inputWidth = 400;
    win.setResizable(true);
    win.setBounds({
      x: screenWidth - inputWidth - 20,
      y: screenHeight - WIDGET_SIZE - 20,
      width: inputWidth,
      height: WIDGET_SIZE
    }, true);
  }
});
electron.ipcMain.on("window-close", () => {
  if (win) {
    win.close();
  }
  electron.app.quit();
});
electron.app.on("window-all-closed", () => {
  if (apiProcess) {
    apiProcess.kill();
  }
  if (process.platform !== "darwin") {
    electron.app.quit();
    win = null;
  }
});
electron.app.on("quit", () => {
  if (apiProcess) {
    apiProcess.kill();
  }
});
electron.app.on("activate", () => {
  if (electron.BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
electron.app.whenReady().then(() => {
  startBackendApi();
  createWindow();
});
exports.MAIN_DIST = MAIN_DIST;
exports.RENDERER_DIST = RENDERER_DIST;
exports.VITE_DEV_SERVER_URL = VITE_DEV_SERVER_URL;
