const pending = new Map();
let sequence = 0;
const listeners = new Set();
export function onProgress(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
const ready = new Promise((resolve, reject) => {
  if (!window.qt?.webChannelTransport || !window.QWebChannel) {
    reject(
      new Error("Open this interface through the SecureRAG desktop launcher."),
    );
    return;
  }
  new window.QWebChannel(window.qt.webChannelTransport, (channel) => {
    const api = channel.objects.desktop;
    api.progress.connect((raw) => {
      const message = JSON.parse(raw);
      listeners.forEach((listener) => listener(message.phase));
    });
    api.response.connect((raw) => {
      const message = JSON.parse(raw),
        job = pending.get(message.id);
      if (!job) return;
      pending.delete(message.id);
      message.error
        ? job.reject(new Error(message.error))
        : job.resolve(message.result);
    });
    resolve(api);
  });
});
export async function call(operation, args = {}) {
  const api = await ready;
  return new Promise((resolve, reject) => {
    const id = String(++sequence);
    pending.set(id, { resolve, reject });
    api.request(JSON.stringify({ id, operation, args }));
  });
}
