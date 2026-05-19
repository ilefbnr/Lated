declare module 'react-cytoscapejs' {
  import type { ComponentType, CSSProperties } from 'react';
  import type {
    Core,
    ElementDefinition,
    LayoutOptions,
  } from 'cytoscape';

  export interface CytoscapeComponentProps {
    elements: ElementDefinition[];
    stylesheet?: Array<{ selector: string; style: Record<string, unknown> }>;
    style?: CSSProperties;
    layout?: LayoutOptions;
    cy?: (cy: Core) => void;
    className?: string;
    autoungrabify?: boolean;
    autounselectify?: boolean;
    boxSelectionEnabled?: boolean;
    minZoom?: number;
    maxZoom?: number;
    panningEnabled?: boolean;
    userPanningEnabled?: boolean;
    userZoomingEnabled?: boolean;
  }

  const CytoscapeComponent: ComponentType<CytoscapeComponentProps>;
  export default CytoscapeComponent;
}
