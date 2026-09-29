/**
 * Purpose: Detect a framed face in a video stream so capture can fire itself.
 * Dependencies: @mediapipe/tasks-vision, loaded on demand.
 * Used by: the guarantor liveness screen.
 *
 * This is a framing aid, not a liveness check: it accepts a photo of a photo
 * quite happily. Anti-spoofing stays with the verification provider.
 */

import type { FaceDetector } from "@mediapipe/tasks-vision";

/** WASM is served from this app; see scripts/copy-mediapipe-wasm.mjs. */
const WASM_ROOT = "/mediapipe/wasm";
/** BlazeFace short-range, hosted by Google. ~230KB, fetched once. */
const MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite";

/** Fraction of the frame width a face must span before it is close enough. */
const MIN_FACE_WIDTH_RATIO = 0.28;
/** Beyond this the face fills too much of the frame. */
const MAX_FACE_WIDTH_RATIO = 0.75;

export type FaceGuidance = "searching" | "move-closer" | "move-back" | "hold-still";

export type DetectionReading = {
  guidance: FaceGuidance;
  /** Face width relative to the frame, handy for tuning the thresholds. */
  widthRatio: number;
};

let detectorPromise: Promise<FaceDetector> | null = null;

/** Load the detector once and share it across mounts. */
export function loadFaceDetector(): Promise<FaceDetector> {
  if (!detectorPromise) {
    detectorPromise = (async () => {
      const vision = await import("@mediapipe/tasks-vision");
      const fileset = await vision.FilesetResolver.forVisionTasks(WASM_ROOT);
      return vision.FaceDetector.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: MODEL_URL, delegate: "GPU" },
        runningMode: "VIDEO",
        minDetectionConfidence: 0.6,
      });
    })().catch((cause) => {
      // Let a later attempt retry rather than caching the failure forever.
      detectorPromise = null;
      throw cause;
    });
  }

  return detectorPromise;
}

/**
 * Read one video frame and say what the guarantor should do next.
 *
 * `timestamp` must increase between calls; pass performance.now().
 */
export function readFrame(
  detector: FaceDetector,
  video: HTMLVideoElement,
  timestamp: number,
): DetectionReading {
  const frameWidth = video.videoWidth || 1;
  const { detections } = detector.detectForVideo(video, timestamp);

  const face = detections[0]?.boundingBox;
  if (!face) return { guidance: "searching", widthRatio: 0 };

  const widthRatio = face.width / frameWidth;
  if (widthRatio < MIN_FACE_WIDTH_RATIO) return { guidance: "move-closer", widthRatio };
  if (widthRatio > MAX_FACE_WIDTH_RATIO) return { guidance: "move-back", widthRatio };

  return { guidance: "hold-still", widthRatio };
}

export const GUIDANCE_COPY: Record<FaceGuidance, string> = {
  searching: "Position your face inside the frame",
  "move-closer": "Move closer",
  "move-back": "Move back a little",
  "hold-still": "Hold still",
};
