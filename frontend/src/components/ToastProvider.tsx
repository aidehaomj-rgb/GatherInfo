import {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  useEffect,
} from "react";
import { X, CheckCircle, Info, AlertTriangle, AlertCircle } from "lucide-react";

type ToastType = "success" | "info" | "warning" | "error";
type ToastPosition = "top-center" | "top-right" | "bottom-right";

interface Toast {
  id: string;
  message: string;
  type: ToastType;
  duration: number;
  position: ToastPosition;
  progress: number;
}

interface ToastOptions {
  type?: ToastType;
  duration?: number;
  position?: ToastPosition;
}

interface ToastContextValue {
  toast: (message: string, opts?: ToastOptions) => void;
  success: (message: string, opts?: Omit<ToastOptions, "type">) => void;
  info: (message: string, opts?: Omit<ToastOptions, "type">) => void;
  warning: (message: string, opts?: Omit<ToastOptions, "type">) => void;
  error: (message: string, opts?: Omit<ToastOptions, "type">) => void;
  dismiss: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let globalId = 0;
function nextId() {
  globalId += 1;
  return `toast-${globalId}`;
}

const ICON_MAP: Record<ToastType, React.ReactNode> = {
  success: <CheckCircle size={18} />,
  info: <Info size={18} />,
  warning: <AlertTriangle size={18} />,
  error: <AlertCircle size={18} />,
};

const TYPE_CLASS: Record<ToastType, string> = {
  success: "toast--success",
  info: "toast--info",
  warning: "toast--warning",
  error: "toast--error",
};

const TYPE_COLOR: Record<ToastType, string> = {
  success: "var(--green)",
  info: "var(--accent)",
  warning: "var(--amber)",
  error: "var(--red)",
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timersRef = useRef<Record<string, number>>({});

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    if (timersRef.current[id]) {
      window.clearInterval(timersRef.current[id]);
      delete timersRef.current[id];
    }
  }, []);

  const addToast = useCallback(
    (message: string, opts: ToastOptions = {}) => {
      const {
        type = "info",
        duration = 4000,
        position = "top-right",
      } = opts;
      const id = nextId();
      const newToast: Toast = {
        id,
        message,
        type,
        duration,
        position,
        progress: 100,
      };
      setToasts((prev) => [...prev, newToast]);

      const start = Date.now();
      const interval = window.setInterval(() => {
        const elapsed = Date.now() - start;
        const remaining = Math.max(0, duration - elapsed);
        const pct = (remaining / duration) * 100;
        if (remaining <= 0) {
          dismiss(id);
        } else {
          setToasts((prev) =>
            prev.map((t) => (t.id === id ? { ...t, progress: pct } : t))
          );
        }
      }, 50);
      timersRef.current[id] = interval;
    },
    [dismiss]
  );

  useEffect(() => {
    return () => {
      Object.values(timersRef.current).forEach((t) => window.clearInterval(t));
      timersRef.current = {};
    };
  }, []);

  const success = useCallback(
    (msg: string, opts?: Omit<ToastOptions, "type">) => addToast(msg, { ...opts, type: "success" }),
    [addToast]
  );
  const info = useCallback(
    (msg: string, opts?: Omit<ToastOptions, "type">) => addToast(msg, { ...opts, type: "info" }),
    [addToast]
  );
  const warning = useCallback(
    (msg: string, opts?: Omit<ToastOptions, "type">) => addToast(msg, { ...opts, type: "warning" }),
    [addToast]
  );
  const error = useCallback(
    (msg: string, opts?: Omit<ToastOptions, "type">) => addToast(msg, { ...opts, type: "error" }),
    [addToast]
  );

  const grouped = toasts.reduce(
    (acc, t) => {
      acc[t.position] = [...(acc[t.position] || []), t];
      return acc;
    },
    {} as Record<ToastPosition, Toast[]>
  );

  return (
    <ToastContext.Provider value={{ toast: addToast, success, info, warning, error, dismiss }}>
      {children}
      {Object.entries(grouped).map(([position, list]) => (
        <div key={position} className={`toast-stack toast-stack--${position}`}>
          {list.map((t) => (
            <div
              key={t.id}
              className={`toast ${TYPE_CLASS[t.type]}`}
              role="alert"
              onMouseEnter={() => {
                if (timersRef.current[t.id]) {
                  window.clearInterval(timersRef.current[t.id]);
                  delete timersRef.current[t.id];
                }
              }}
              onMouseLeave={() => {
                const start = Date.now() - (t.duration * (100 - t.progress)) / 100;
                const interval = window.setInterval(() => {
                  const elapsed = Date.now() - start;
                  const remaining = Math.max(0, t.duration - elapsed);
                  const pct = (remaining / t.duration) * 100;
                  if (remaining <= 0) {
                    dismiss(t.id);
                  } else {
                    setToasts((prev) =>
                      prev.map((x) => (x.id === t.id ? { ...x, progress: pct } : x))
                    );
                  }
                }, 50);
                timersRef.current[t.id] = interval;
              }}
            >
              <div className="toast-icon" style={{ color: TYPE_COLOR[t.type] }}>
                {ICON_MAP[t.type]}
              </div>
              <div className="toast-content">{t.message}</div>
              <button
                type="button"
                className="toast-close"
                onClick={() => dismiss(t.id)}
                aria-label="关闭"
              >
                <X size={14} />
              </button>
              <div
                className="toast-progress"
                style={{
                  width: `${t.progress}%`,
                  background: TYPE_COLOR[t.type],
                }}
              />
            </div>
          ))}
        </div>
      ))}
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return ctx;
}
