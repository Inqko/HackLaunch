import { Minus, Plus } from "lucide-react";
import { useEffect, useRef, useState, type PointerEvent } from "react";
import { Button, ErrorText, Modal, Spinner } from "./ui";

const OUTPUT_SIZE = 512;
const MAX_ZOOM = 4;
const PREVIEW_SIZE = 64;

interface Loaded {
  img: HTMLImageElement;
  url: string;
}

/** Положение рамки: zoom ≥ 1 и центр рамки в долях ширины/высоты исходного фото */
interface Crop {
  zoom: number;
  cx: number;
  cy: number;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

/** Не даём рамке выйти за края фото */
function clampCrop(crop: Crop, w: number, h: number): Crop {
  const zoom = clamp(crop.zoom, 1, MAX_ZOOM);
  const half = Math.min(w, h) / zoom / 2;
  return {
    zoom,
    cx: clamp(crop.cx * w, half, w - half) / w,
    cy: clamp(crop.cy * h, half, h - half) / h,
  };
}

/** Квадрат в пикселях исходного фото, который попадает в рамку */
function sourceRect(crop: Crop, w: number, h: number) {
  const side = Math.min(w, h) / crop.zoom;
  return { sx: crop.cx * w - side / 2, sy: crop.cy * h - side / 2, side };
}

function imageStyle(crop: Crop, w: number, h: number, frame: number) {
  // Сколько экранных пикселей приходится на пиксель фото
  const k = (frame / Math.min(w, h)) * crop.zoom;
  return {
    width: w * k,
    height: h * k,
    left: `calc(50% - ${crop.cx * w * k}px)`,
    top: `calc(50% - ${crop.cy * h * k}px)`,
  };
}

export function AvatarCropModal({
  file,
  onClose,
  onConfirm,
}: {
  file: File | null;
  onClose: () => void;
  onConfirm: (cropped: File) => Promise<void>;
}) {
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [crop, setCrop] = useState<Crop>({ zoom: 1, cx: 0.5, cy: 0.5 });
  const [frame, setFrame] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const frameRef = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number; y: number; crop: Crop } | null>(null);

  useEffect(() => {
    setLoaded(null);
    setError("");
    setCrop({ zoom: 1, cx: 0.5, cy: 0.5 });
    if (!file) return;
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => setLoaded({ img, url });
    img.onerror = () => setError("Не удалось открыть изображение");
    img.src = url;
    return () => URL.revokeObjectURL(url);
  }, [file]);

  // Размер рамки зависит от ширины экрана, пересчитываем при ресайзе
  useEffect(() => {
    const el = frameRef.current;
    if (!el) return;
    const observer = new ResizeObserver(() => setFrame(el.clientWidth));
    observer.observe(el);
    return () => observer.disconnect();
  }, [loaded]);

  // React вешает wheel пассивно, а нам нужен preventDefault, чтобы не скроллить страницу
  useEffect(() => {
    const el = frameRef.current;
    if (!el || !loaded) return;
    const { naturalWidth: w, naturalHeight: h } = loaded.img;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      setCrop((c) => clampCrop({ ...c, zoom: c.zoom * Math.exp(-e.deltaY / 500) }, w, h));
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [loaded]);

  if (!file) return null;

  const w = loaded?.img.naturalWidth ?? 1;
  const h = loaded?.img.naturalHeight ?? 1;
  const setZoom = (zoom: number) => setCrop((c) => clampCrop({ ...c, zoom }, w, h));

  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = { x: e.clientX, y: e.clientY, crop };
  };

  const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
    const start = drag.current;
    if (!start || !frame) return;
    const k = (frame / Math.min(w, h)) * start.crop.zoom;
    setCrop(
      clampCrop(
        {
          zoom: start.crop.zoom,
          cx: start.crop.cx - (e.clientX - start.x) / (k * w),
          cy: start.crop.cy - (e.clientY - start.y) / (k * h),
        },
        w,
        h,
      ),
    );
  };

  const onPointerUp = () => {
    drag.current = null;
  };

  const save = async () => {
    if (!loaded) return;
    setSaving(true);
    setError("");
    try {
      const { sx, sy, side } = sourceRect(crop, w, h);
      const canvas = document.createElement("canvas");
      canvas.width = canvas.height = OUTPUT_SIZE;
      canvas.getContext("2d")!.drawImage(loaded.img, sx, sy, side, side, 0, 0, OUTPUT_SIZE, OUTPUT_SIZE);
      // PNG сохраняет прозрачность, остальное жмём в JPEG
      const type = file.type === "image/png" ? "image/png" : "image/jpeg";
      const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, type, 0.9));
      if (!blob) throw new Error("Не удалось обработать изображение");
      await onConfirm(new File([blob], type === "image/png" ? "avatar.png" : "avatar.jpg", { type }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const preview = loaded ? imageStyle(crop, w, h, PREVIEW_SIZE) : null;

  return (
    <Modal open title="Выберите область фото" onClose={saving ? () => {} : onClose}>
      {!loaded && !error && (
        <div className="flex h-64 items-center justify-center">
          <Spinner />
        </div>
      )}
      {loaded && (
        <div className="space-y-4">
          {/* Отступ вокруг рамки показывает затемнённую часть фото, которая не попадёт в аватар */}
          <div className="mx-auto w-full max-w-xs overflow-hidden rounded-lg bg-slate-900 p-6">
            <div
              ref={frameRef}
              className="relative aspect-square w-full cursor-move touch-none select-none"
              onPointerDown={onPointerDown}
              onPointerMove={onPointerMove}
              onPointerUp={onPointerUp}
              onPointerCancel={onPointerUp}
            >
              {frame > 0 && (
                <img
                  src={loaded.url}
                  alt=""
                  draggable={false}
                  className="pointer-events-none absolute max-w-none opacity-40"
                  style={imageStyle(crop, w, h, frame)}
                />
              )}
              <div className="pointer-events-none absolute inset-0 overflow-hidden">
                {frame > 0 && (
                  <img
                    src={loaded.url}
                    alt=""
                    draggable={false}
                    className="absolute max-w-none"
                    style={imageStyle(crop, w, h, frame)}
                  />
                )}
              </div>
              <div className="pointer-events-none absolute inset-0 border-2 border-white shadow-[0_0_0_1px_rgba(0,0,0,0.3)]">
                <div className="absolute inset-y-0 left-1/3 w-px bg-white/40" />
                <div className="absolute inset-y-0 left-2/3 w-px bg-white/40" />
                <div className="absolute inset-x-0 top-1/3 h-px bg-white/40" />
                <div className="absolute inset-x-0 top-2/3 h-px bg-white/40" />
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setZoom(crop.zoom / 1.2)}
              className="rounded p-1 text-slate-500 hover:bg-slate-100"
              aria-label="Уменьшить"
            >
              <Minus className="h-4 w-4" />
            </button>
            <input
              type="range"
              min={1}
              max={MAX_ZOOM}
              step={0.01}
              value={crop.zoom}
              onChange={(e) => setZoom(Number(e.target.value))}
              className="flex-1 accent-indigo-600"
              aria-label="Масштаб"
            />
            <button
              type="button"
              onClick={() => setZoom(crop.zoom * 1.2)}
              className="rounded p-1 text-slate-500 hover:bg-slate-100"
              aria-label="Увеличить"
            >
              <Plus className="h-4 w-4" />
            </button>
          </div>

          <div className="flex items-center gap-3 text-sm text-slate-500">
            <div className="relative h-16 w-16 shrink-0 overflow-hidden rounded-full bg-slate-100">
              {preview && <img src={loaded.url} alt="" className="absolute max-w-none" style={preview} />}
            </div>
            Так фото будет выглядеть в профиле. Перетащите снимок, чтобы выбрать область.
          </div>
        </div>
      )}
      {error && (
        <div className="mt-4">
          <ErrorText>{error}</ErrorText>
        </div>
      )}
      <div className="mt-6 flex justify-end gap-2">
        <Button variant="outline" onClick={onClose} disabled={saving}>
          Отмена
        </Button>
        <Button onClick={save} disabled={!loaded || saving}>
          {saving ? "Сохраняем…" : "Сохранить"}
        </Button>
      </div>
    </Modal>
  );
}
