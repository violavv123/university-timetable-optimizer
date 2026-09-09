import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getErrorMessage } from "../lib/api-error";
import { timetableService } from "../services/timetable.service";
import type { GenerationRequest, TimetableRun } from "../types";

type GenerationStatus = "idle" | "running" | "succeeded" | "failed";

interface GenerationTask {
  status: GenerationStatus;
  request: GenerationRequest | null;
  facultyName: string;
  result: TimetableRun | null;
  errorMessage: string;
  startedAt: number | null;
  elapsedSeconds: number;
}

interface GenerationContextValue extends GenerationTask {
  startGeneration: (request: GenerationRequest, facultyName: string) => void;
  dismiss: () => void;
}

const idleTask: GenerationTask = {
  status: "idle",
  request: null,
  facultyName: "",
  result: null,
  errorMessage: "",
  startedAt: null,
  elapsedSeconds: 0,
};

const GenerationContext = createContext<GenerationContextValue | null>(null);

export function GenerationProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [task, setTask] = useState<GenerationTask>(idleTask);

  useEffect(() => {
    if (task.status !== "running" || task.startedAt === null) return;
    const updateElapsed = () => {
      setTask((current) =>
        current.status === "running" && current.startedAt !== null
          ? {
              ...current,
              elapsedSeconds: Math.max(
                0,
                Math.floor((Date.now() - current.startedAt) / 1000),
              ),
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
      const startedAt = Date.now();
      setTask({
        status: "running",
        request,
        facultyName,
        result: null,
        errorMessage: "",
        startedAt,
        elapsedSeconds: 0,
      });

      void timetableService
        .generate(request)
        .then((result) => {
          setTask((current) => ({
            ...current,
            status: "succeeded",
            result,
            elapsedSeconds: Math.max(
              0,
              Math.floor((Date.now() - startedAt) / 1000),
            ),
          }));
          void queryClient.invalidateQueries({ queryKey: ["runs"] });
          document.title = "Timetable ready — Tempo";
        })
        .catch((error: unknown) => {
          setTask((current) => ({
            ...current,
            status: "failed",
            errorMessage: getErrorMessage(error),
            elapsedSeconds: Math.max(
              0,
              Math.floor((Date.now() - startedAt) / 1000),
            ),
          }));
          void queryClient.invalidateQueries({ queryKey: ["runs"] });
          document.title = "Generation failed — Tempo";
        });
    },
    [queryClient, task.status],
  );

  const dismiss = useCallback(() => setTask(idleTask), []);
  const value = useMemo(
    () => ({ ...task, startGeneration, dismiss }),
    [task, startGeneration, dismiss],
  );

  return (
    <GenerationContext.Provider value={value}>
      {children}
    </GenerationContext.Provider>
  );
}

export function useGeneration() {
  const context = useContext(GenerationContext);
  if (!context) {
    throw new Error("useGeneration must be used within GenerationProvider");
  }
  return context;
}
