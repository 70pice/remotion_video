import { useCallback, useEffect, useRef, useState } from "react";
import { api, explainError } from "./client";
import type { Job } from "./types";

// SSE is an acceleration; the persisted job remains the authority after reconnect.
export function useJob(jobId: string) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState("");
  const [live, setLive] = useState(false);
  const latestEventId = useRef(0);
  const currentJobId = useRef(jobId);
  const generation = useRef(0);
  const sequence = useRef(0);
  const appliedSequence = useRef(0);
  currentJobId.current = jobId;
  const refresh = useCallback(async () => {
    const requestGeneration = generation.current;
    const requestSequence = ++sequence.current;
    try {
      const next = await api.job(jobId);
      if (
        currentJobId.current !== jobId ||
        generation.current !== requestGeneration ||
        requestSequence < appliedSequence.current
      )
        return null;
      appliedSequence.current = requestSequence;
      setJob((current) => chooseLatestJob(current, next));
      latestEventId.current = Math.max(
        latestEventId.current,
        next.latest_event_id,
      );
      setError("");
      return next;
    } catch (cause) {
      if (
        currentJobId.current !== jobId ||
        generation.current !== requestGeneration ||
        requestSequence < appliedSequence.current
      )
        return null;
      appliedSequence.current = requestSequence;
      setError(explainError(cause));
      return null;
    }
  }, [jobId]);

  useEffect(() => {
    generation.current += 1;
    let active = true;
    let stream: EventSource | null = null;
    let reconnect: ReturnType<typeof setTimeout> | undefined;
    let debounce: ReturnType<typeof setTimeout> | undefined;
    setJob(null);
    setLive(false);
    latestEventId.current = 0;
    const connect = async () => {
      await refresh();
      if (!active) return;
      stream = new EventSource(
        `/api/jobs/${encodeURIComponent(jobId)}/events?after=${latestEventId.current}`,
      );
      stream.onopen = () => {
        if (active) setLive(true);
      };
      stream.addEventListener("progress", (event) => {
        if (!active) return;
        latestEventId.current = Math.max(
          latestEventId.current,
          Number((event as MessageEvent).lastEventId) || 0,
        );
        clearTimeout(debounce);
        debounce = setTimeout(() => {
          if (active) void refresh();
        }, 120);
      });
      stream.onerror = () => {
        if (!active) return;
        setLive(false);
        stream?.close();
        if (active)
          reconnect = setTimeout(() => {
            void connect();
          }, 3000);
      };
    };
    void connect();
    const polling = setInterval(() => {
      if (active) void refresh();
    }, 5000);
    return () => {
      generation.current += 1;
      active = false;
      stream?.close();
      clearTimeout(reconnect);
      clearTimeout(debounce);
      clearInterval(polling);
    };
  }, [jobId, refresh]);

  return { job, setJob, error, live, refresh };
}

export function chooseLatestJob(current: Job | null, next: Job): Job {
  if (!current || current.job_id !== next.job_id) return next;
  if (current.revision !== next.revision)
    return current.revision > next.revision ? current : next;
  if (current.latest_event_id !== next.latest_event_id)
    return current.latest_event_id > next.latest_event_id ? current : next;
  if (current.updated_at > next.updated_at) return current;
  return next;
}
