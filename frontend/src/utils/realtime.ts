/**
 * 前端 WebSocket 客户端 -- 实时行情推送。
 *
 * 连接后端 ws://host/ws/realtime，订阅/取消订阅加密货币实时行情。
 * 自动重连 + 心跳保活。
 */

type QuoteCallback = (code: string, data: any) => void;

export class RealtimeClient {
  private ws: WebSocket | null = null;
  private url: string;
  private subscribers = new Map<string, Set<QuoteCallback>>();
  private reconnectAttempts = 0;
  private reconnectTimer: number | null = null;
  private heartbeatTimer: number | null = null;
  private running = false;

  constructor(url?: string) {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    this.url = url || `${proto}//${window.location.host}/ws/realtime`;
  }

  connect(): void {
    if (this.running) return;
    this.running = true;
    this._doConnect();
  }

  disconnect(): void {
    this.running = false;
    if (this.reconnectTimer) { clearTimeout(this.reconnectTimer); this.reconnectTimer = null; }
    if (this.heartbeatTimer) { clearInterval(this.heartbeatTimer); this.heartbeatTimer = null; }
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.close();
      this.ws = null;
    }
  }

  subscribe(code: string, callback: QuoteCallback): void {
    if (!this.subscribers.has(code)) {
      this.subscribers.set(code, new Set());
    }
    this.subscribers.get(code)!.add(callback);

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this._send({ action: "subscribe", symbols: [code] });
    }
  }

  unsubscribe(code: string, callback?: QuoteCallback): void {
    if (callback) {
      this.subscribers.get(code)?.delete(callback);
    }
    if (!callback || !this.subscribers.get(code)?.size) {
      this.subscribers.delete(code);
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this._send({ action: "unsubscribe", symbols: [code] });
      }
    }
  }

  get connected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  private _doConnect(): void {
    try {
      this.ws = new WebSocket(this.url);
    } catch {
      this._scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this._startHeartbeat();
      // 重新订阅所有
      const codes = Array.from(this.subscribers.keys());
      if (codes.length > 0) {
        this._send({ action: "subscribe", symbols: codes });
      }
    };

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "quote" && msg.code) {
          const callbacks = this.subscribers.get(msg.code);
          if (callbacks) {
            callbacks.forEach((cb) => cb(msg.code, msg.data));
          }
        }
      } catch {
        // ignore non-JSON
      }
    };

    this.ws.onclose = () => {
      this.ws = null;
      if (this.heartbeatTimer) { clearInterval(this.heartbeatTimer); this.heartbeatTimer = null; }
      if (this.running) this._scheduleReconnect();
    };

    this.ws.onerror = () => {
      // onclose will handle reconnect
    };
  }

  private _scheduleReconnect(): void {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    const delay = Math.min(1000 * 2 ** this.reconnectAttempts, 30000);
    this.reconnectAttempts++;
    this.reconnectTimer = window.setTimeout(() => this._doConnect(), delay);
  }

  private _startHeartbeat(): void {
    if (this.heartbeatTimer) clearInterval(this.heartbeatTimer);
    this.heartbeatTimer = window.setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this._send({ action: "health" });
      }
    }, 30000);
  }

  private _send(data: any): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }
}

let _client: RealtimeClient | null = null;

export function getRealtimeClient(): RealtimeClient {
  if (!_client) {
    _client = new RealtimeClient();
  }
  return _client;
}
