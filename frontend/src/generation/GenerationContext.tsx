import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { timetableService } from "../services/timetable.service";
import { catalogService } from "../services/catalog.service";
import { getErrorMessage } from "../lib/api-error";
import type { GenerationRequest, TimetableRun } from "../types";

type GenerationStatus = "idle" | "running" | "succeeded" | "failed";

interface GenerationTask {
  status: GenerationStatus;
  request: GenerationRequest | null;
  facultyName: string;
  results: TimetableRun[];
  selectedResultId: number | null;
  errorMessage: string;
  startedAt: number | null;
  elapsedSeconds: number;
  stage: string;
}

interface GenerationContextValue extends GenerationTask {
  startGeneration: (request: GenerationRequest, facultyName: string) => void;
  abortGeneration: () => void;
  selectResult: (runId: number) => void;
  dismiss: () => void;
}

const idleTask: GenerationTask = {
  status: "idle",
  request: null,
  facultyName: "",
  results: [],
  selectedResultId: null,
  errorMessage: "",
  startedAt: null,
  elapsedSeconds: 0,
  stage: "",
};

const GenerationContext = createContext<GenerationContextValue | null>(null);

export function GenerationProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [task, setTask] = useState<GenerationTask>(idleTask);
  const activeRunId = useRef<number | null>(null);
  const activeGeneration = useRef(0);
  const abortController = useRef<AbortController | null>(null);

  useEffect(() => {
    if (task.status !== "running" || task.startedAt === null) return;
    const updateElapsed = () => {
      setTask((current) =>
        current.status === "running" && current.startedAt !== null
          ? {
              ...current,
              elapsedSeconds: Math.max(0, Math.floor((Date.now() - current.startedAt) / 1000)),
            }
          : current,
      );
    };
    updateElapsed();
    const timer = window.setInterval(updateElapsed, 1000);
    return () => window.clearInterval(timer);
  }, [task.status, task.startedAt]);

  const startGeneration = useCallback(
    (request: GenerationRequest, facultyName: string) => {
      if (task.status === "running") return;
      const generationId = activeGeneration.current + 1;
      activeGeneration.current = generationId;
      const controller = new AbortController();
      abortController.current = controller;
      activeRunId.current = null;
      const startedAt = Date.now();
      setTask({
        ...idleTask,
        status: "running",
        request,
        facultyName,
        startedAt,
        stage: "Generating timetable",
      });

      void (async () => {
        let completed: TimetableRun[] = [];
        let finalError = "";
        try {
          const result = await timetableService.generate(request);
          activeRunId.current = result.id;
          if (controller.signal.aborted || generationId !== activeGeneration.current) {
            void timetableService.cancel(result.id).catch(() => undefined);
            return;
          }
          let finalRun = result;
          while (!controller.signal.aborted && !["SUCCEEDED", "INFEASIBLE", "FAILED", "CANCELLED"].includes(finalRun.status)) {
            await new Promise<void>((resolve, reject) => {
              const timer = window.setTimeout(resolve, 1000);
              controller.signal.addEventListener("abort", () => {
                window.clearTimeout(timer);
                reject(new DOMException("Generation aborted", "AbortError"));
              }, { once: true });
            });
            finalRun = await catalogService.run(result.id);
          }
          if (finalRun.status === "SUCCEEDED") {
            completed = [finalRun];
          } else if (finalRun.status === "CANCELLED") {
            finalError = "Generation cancelled.";
          } else {
            finalError = `Generation ended with status ${finalRun.status.toLowerCase()}. Try a faster strategy or increase the time limit slightly.`;
          }
        } catch (error) {
          if (controller.signal.aborted || generationId !== activeGeneration.current) return;
          finalError = getErrorMessage(error);
        }
        if (controller.signal.aborted || generationId !== activeGeneration.current) return;
        setTask((current) => ({
          ...current,
          status: completed.length ? "succeeded" : "failed",
          results: completed,
          selectedResultId: completed[0]?.id ?? null,
          errorMessage: finalError,
          stage: "Results ready",
          elapsedSeconds: Math.max(0, Math.floor((Date.now() - startedAt) / 1000)),
        }));
        void queryClient.invalidateQueries({ queryKey: ["runs"] });
        document.title = completed.length ? "Timetable ready — Time's UP" : "Generation failed — Time's UP";
        activeRunId.current = null;
        abortController.current = null;
      })();
    },
    [queryClient, task.status],
  );

  const abortGeneration = useCallback(() => {
    if (task.status !== "running") return;
    activeGeneration.current += 1;
    abortController.current?.abort();
    const runId = activeRunId.current;
    activeRunId.current = null;
    if (runId !== null) {
      void timetableService.cancel(runId).catch(() => undefined);
    }
    setTask((current) => ({
      ...current,
      status: "failed",
      errorMessage: "Generation cancelled.",
      stage: "Generation cancelled",
    }));
    void queryClient.invalidateQueries({ queryKey: ["runs"] });
    document.title = "Generation cancelled — Time's UP";
  }, [queryClient, task.status]);

  const selectResult = useCallback((runId: number) => {
    setTask((current) => ({ ...current, selectedResultId: runId }));
  }, []);

  const dismiss = useCallback(() => setTask(idleTask), []);
  const value = useMemo(
    () => ({ ...task, startGeneration, abortGeneration, selectResult, dismiss }),
    [task, startGeneration, abortGeneration, selectResult, dismiss],
  );

  return <GenerationContext.Provider value={value}>{children}</GenerationContext.Provider>;
}

export function useGeneration() {
  const context = useContext(GenerationContext);
  if (!context) throw new Error("useGeneration must be used within GenerationProvider");
  return context;
}
