"use client";

import {
  type ReactNode,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

interface MeasuredChartFrameProps {
  height: number;
  className?: string;
  children: (size: { width: number; height: number }) => ReactNode;
}

export function MeasuredChartFrame({
  height,
  className,
  children,
}: MeasuredChartFrameProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);

  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) return;

    const updateWidth = () => {
      setWidth(Math.max(0, Math.floor(node.getBoundingClientRect().width)));
    };

    updateWidth();
    const observer = new ResizeObserver(updateWidth);
    observer.observe(node);

    return () => observer.disconnect();
  }, []);

  return (
    <div ref={ref} className={className} style={{ height, minWidth: 0 }}>
      {width > 0 ? children({ width, height }) : null}
    </div>
  );
}
