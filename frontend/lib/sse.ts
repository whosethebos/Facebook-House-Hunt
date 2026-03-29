// frontend/lib/sse.ts
"use client";
import { useEffect, useRef, useState, useCallback } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type SSEEvent =
  | { event: "status"; data: { message: string; status: string } }
  | { event: "listing"; data: Record<string, unknown> }
  | { event: "complete"; data: { total: number; high_match?: number; status: string } }
  | { event: "error"; data: { message: string } };

export function useSSE(searchId: string | null) {
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isDone, setIsDone] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  const connect = useCallback(() => {
    if (!searchId || esRef.current) return;

    const es = new EventSource(`${API}/searches/${searchId}/stream`);
    esRef.current = es;
    setIsConnected(true);

    const handleEvent = (eventName: string) => (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        setEvents(prev => [...prev, { event: eventName, data } as SSEEvent]);
        if (eventName === "complete" || eventName === "error") {
          setIsDone(true);
          es.close();
          esRef.current = null;
          setIsConnected(false);
        }
      } catch {
        // ignore parse errors
      }
    };

    es.addEventListener("status", handleEvent("status"));
    es.addEventListener("listing", handleEvent("listing"));
    es.addEventListener("complete", handleEvent("complete"));
    es.addEventListener("error", handleEvent("error"));

    es.onerror = () => {
      setIsConnected(false);
      es.close();
      esRef.current = null;
    };
  }, [searchId]);

  useEffect(() => {
    connect();
    return () => {
      esRef.current?.close();
      esRef.current = null;
    };
  }, [connect]);

  const statusMessages = events
    .filter(e => e.event === "status")
    .map(e => (e as { event: "status"; data: { message: string; status: string } }).data.message);

  const listings = events
    .filter(e => e.event === "listing")
    .map(e => (e as { event: "listing"; data: Record<string, unknown> }).data);

  const completeEvent = events.find(e => e.event === "complete") as
    | { event: "complete"; data: { total: number; high_match?: number; status: string } }
    | undefined;

  const errorEvent = events.find(e => e.event === "error") as
    | { event: "error"; data: { message: string } }
    | undefined;

  return { statusMessages, listings, completeEvent, errorEvent, isConnected, isDone };
}
