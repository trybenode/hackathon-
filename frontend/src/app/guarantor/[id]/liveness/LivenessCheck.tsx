"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button, CheckIcon, Modal } from "@/components/ui";
import { cn } from "@/lib/cn";
import {
  GUIDANCE_COPY,
  loadFaceDetector,
  readFrame,
  type FaceGuidance,
} from "@/lib/faceDetection";
import { ApiError, getInstrument, submitLiveness } from "@/lib/guarantor";

type Stage = "idle" | "capturing" | "checking" | "verified" | "error";

/** JPEG quality for the captured frame: enough for a provider, small to send. */
const FRAME_QUALITY = 0.85;
/** How long the face must stay well framed before capture fires. */
const HOLD_STILL_MS = 1500;

export function LivenessCheck({ instrumentId }: { instrumentId: string }) {
  const router = useRouter();
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [stage, setStage] = useState<Stage>("idle");
  const [error, setError] = useState<string | null>(null);
  const [guidance, setGuidance] = useState<FaceGuidance>("searching");
  /** Kept after a failed upload so the same shot can be retried. */
  const capturedRef = useRef<Blob | null>(null);
  /** Mirrors capturedRef for rendering, since refs cannot be read in render. */
  const [hasCapture, setHasCapture] = useState(false);
  /** False when detection is unavailable, so capture stays manual. */
  const [autoCapture, setAutoCapture] = useState(true);
  const [detectorReady, setDetectorReady] = useState(false);
  const captureRef = useRef<() => Promise<void>>(null);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  // Send the guarantor back if the instrument is not awaiting verification.
  useEffect(() => {
    let cancelled = false;

    async function guard() {
      try {
        const instrument = await getInstrument(instrumentId);
        if (cancelled) return;
        if (instrument.status === "Pending Signature") {
          router.replace(`/guarantor/${instrumentId}/review`);
        } else if (instrument.status === "Active") {
          setStage("verified");
        } else if (instrument.status !== "Pending Verification") {
          setError("This request is no longer awaiting verification.");
        }
      } catch {
        if (!cancelled) setError("Could not load this request.");
      }
    }

    void guard();
    return () => {
      cancelled = true;
    };
  }, [instrumentId, router]);

  useEffect(() => stopCamera, [stopCamera]);

  // Warm the detector while the guarantor reads the instructions, so Begin is
  // not followed by a model download. Failure just means manual capture.
  useEffect(() => {
    let cancelled = false;

    loadFaceDetector()
      .then(() => {
        if (!cancelled) setDetectorReady(true);
      })
      .catch(() => {
        if (!cancelled) setAutoCapture(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  // Watch the stream and fire capture once the face holds steady in frame.
  useEffect(() => {
    if (stage !== "capturing") return;

    let frameId = 0;
    let cancelled = false;
    let steadySince: number | null = null;

    async function watch() {
      let detector;
      try {
        detector = await loadFaceDetector();
      } catch {
        // No detector: leave the guarantor with the manual Capture button.
        if (!cancelled) setAutoCapture(false);
        return;
      }

      const tick = () => {
        if (cancelled) return;
        const video = videoRef.current;

        if (video && video.readyState >= 2) {
          const reading = readFrame(detector, video, performance.now());
          setGuidance(reading.guidance);

          if (reading.guidance === "hold-still") {
            steadySince ??= performance.now();
            if (performance.now() - steadySince >= HOLD_STILL_MS) {
              cancelled = true;
              void captureRef.current?.();
              return;
            }
          } else {
            steadySince = null;
          }
        }

        frameId = requestAnimationFrame(tick);
      };

      frameId = requestAnimationFrame(tick);
    }

    void watch();
    return () => {
      cancelled = true;
      cancelAnimationFrame(frameId);
    };
  }, [stage]);

  async function begin() {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user" },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setGuidance("searching");
      setStage("capturing");
    } catch {
      setStage("error");
      setError("We could not reach your camera. Allow camera access and try again.");
    }
  }

  const capture = useCallback(async function capture() {
    const video = videoRef.current;
    if (!video) return;

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth || 480;
    canvas.height = video.videoHeight || 640;
    canvas.getContext("2d")?.drawImage(video, 0, 0, canvas.width, canvas.height);

    const frame = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", FRAME_QUALITY),
    );
    if (!frame) {
      setError("Could not read the camera frame. Try again.");
      return;
    }

    capturedRef.current = frame;
    setHasCapture(true);
    setStage("checking");
    stopCamera();

    try {
      await submitLiveness(instrumentId, frame);
      capturedRef.current = null;
      setHasCapture(false);
      setStage("verified");
    } catch (cause) {
      setStage("error");
      setError(
        cause instanceof ApiError ? cause.message : "Could not complete the check. Try again.",
      );
    }
  }, [instrumentId, stopCamera]);

  /** Resend the frame already taken, so a dropped request costs no re-shoot. */
  const retryUpload = useCallback(async () => {
    const frame = capturedRef.current;
    if (!frame) return;

    setStage("checking");
    setError(null);

    try {
      await submitLiveness(instrumentId, frame);
      capturedRef.current = null;
      setHasCapture(false);
      setStage("verified");
    } catch (cause) {
      setStage("error");
      setError(
        cause instanceof ApiError ? cause.message : "Could not complete the check. Try again.",
      );
    }
  }, [instrumentId]);

  // Keep the ref pointing at the latest capture so the detection loop can call
  // it without listing capture as a dependency and restarting itself.
  useEffect(() => {
    captureRef.current = capture;
  }, [capture]);

  return (
    <main
      className="mx-auto flex w-full max-w-md flex-col"
      // Surfaced so the capture path can be checked without a camera.
      data-detector={detectorReady ? "ready" : autoCapture ? "loading" : "unavailable"}
    >
      <div className="h-28 w-full rounded-b-xl bg-info-light" />

      <div className="flex flex-col gap-2 px-6 pt-8">
        <h1 className="text-body-lg font-semibold text-grey-900">Liveness check</h1>
        <p className="text-body-sm text-grey-600">
          Position your face inside the frame, Follow the instructions on the screen
        </p>
      </div>

      <div className="flex flex-col items-center gap-8 px-6 pt-10 pb-12">
        <p className="text-body-md text-grey-900">
          {stage === "capturing" ? GUIDANCE_COPY[guidance] : "Move closer"}
        </p>

        <div
          className={cn(
            "flex h-48 w-40 items-center justify-center overflow-hidden bg-info-light",
            // The design frames the face in an oval.
            "rounded-[50%]",
          )}
        >
          <video
            ref={videoRef}
            playsInline
            muted
            className={cn("h-full w-full object-cover", stage !== "capturing" && "hidden")}
          />
          {stage !== "capturing" && (
            <span className="text-body-sm text-grey-600">Camera off</span>
          )}
        </div>

        {error && (
          <p role="alert" className="text-center text-body-sm text-error">
            {error}
          </p>
        )}

        {stage === "capturing" ? (
          autoCapture ? (
            <p className="text-body-sm text-grey-600">
              Capturing automatically once your face is steady
            </p>
          ) : (
            <Button size="lg" className="rounded-pill px-12" onClick={capture}>
              Capture
            </Button>
          )
        ) : stage === "error" && hasCapture ? (
          <div className="flex flex-col items-center gap-3">
            <Button size="lg" className="rounded-pill px-12" onClick={retryUpload}>
              Retry
            </Button>
            <button
              type="button"
              onClick={begin}
              className="text-body-sm text-grey-600 underline"
            >
              Take a new photo
            </button>
          </div>
        ) : (
          <Button
            size="lg"
            className="rounded-pill px-12"
            disabled={stage === "checking" || stage === "verified"}
            onClick={begin}
          >
            {stage === "error" ? "Try again" : "Begin"}
          </Button>
        )}
      </div>

      <Modal open={stage === "checking"} title="Verifying your identity…" hideTitle>
        <span className="h-12 w-12 animate-spin rounded-pill border-4 border-primary-100 border-t-primary-400" />
        <h2 className="text-h3 text-grey-900">Verifying your identity...</h2>
        <p className="text-body-md text-grey-600">
          We&rsquo;re securely checking your details. This should only take a moment
        </p>
      </Modal>

      <Modal open={stage === "verified"} title="Verified" hideTitle>
        <span className="flex h-14 w-14 items-center justify-center rounded-pill bg-primary-400">
          <CheckIcon className="text-white" width={28} height={28} />
        </span>
        <h2 className="text-h3 text-grey-900">Verified</h2>
        <p className="text-body-md text-grey-600">
          Your identity has been verified successfully!
        </p>
        <Button
          size="lg"
          className="mt-2 rounded-pill px-10"
          onClick={() => router.push("/dashboard")}
        >
          Get started
        </Button>
      </Modal>
    </main>
  );
}
