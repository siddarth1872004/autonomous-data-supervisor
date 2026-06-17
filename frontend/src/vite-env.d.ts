/// <reference types="vite/client" />

// Extend window for dynamically loaded Plotly UMD bundle
interface PlotlyStatic {
  newPlot(
    element: HTMLElement,
    data: unknown[],
    layout?: unknown,
    config?: unknown
  ): Promise<void>;
  react(
    element: HTMLElement,
    data: unknown[],
    layout?: unknown,
    config?: unknown
  ): Promise<void>;
  purge(element: HTMLElement): void;
}

declare global {
  interface Window {
    Plotly: PlotlyStatic;
  }
}
