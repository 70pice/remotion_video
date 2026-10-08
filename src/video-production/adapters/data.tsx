import {useCurrentFrame} from 'remotion';
import type {DataItem} from '../types';
import {DataBars, DataDonuts, type DataVisualization} from './dataCharts';
import {Body, Card, CuedMotion, FittedText, Motion, SceneHeader, muted, useLayout, white} from './layout';
import type {AdapterProps} from './layout';

type DataAdapterProps = {
  items?: DataItem[];
  visualization?: DataVisualization;
  scale_max?: number;
  unit?: string;
  reference_value?: number;
};

const RevealedValue = ({item, width, height, delay}: {item: DataItem; width: number; height: number; delay: number}) => {
  const {unit} = useLayout();
  return <CuedMotion revealFrame={item.reveal_frame} delay={delay}>
    <FittedText text={item.value} width={width} height={height}
      fontSize={96 * unit} minFontSize={24 * unit} lineHeight={1.12} style={{margin: 0, color: white}} />
  </CuedMotion>;
};

const DataValue = ({item, width, height, delay}: {item: DataItem; width: number; height: number; delay: number}) => {
  const frame = useCurrentFrame();
  const {unit} = useLayout();
  const revealed = item.reveal_frame === undefined || frame >= item.reveal_frame;
  if (!revealed) return null;
  return <div data-data-value style={{height, margin: `${12 * unit}px 0`}}>
    <RevealedValue item={item} width={width} height={height} delay={delay} />
  </div>;
};

const DataCard = ({item, cardHeight, innerWidth, delay, accent}: {
  item: DataItem; cardHeight: number; innerWidth: number; delay: number; accent: string;
}) => {
  const frame = useCurrentFrame();
  const {unit} = useLayout();
  const pending = item.reveal_frame !== undefined && frame < item.reveal_frame;
  const usableHeight = cardHeight - 92 * unit;
  const labelHeight = usableHeight * (pending ? item.detail ? 0.54 : 0.82 : 0.27);
  const valueHeight = usableHeight * (item.detail ? 0.43 : 0.7);
  const detailHeight = usableHeight * (pending ? item.detail ? 0.34 : 0 : 0.3);
  return <Card accent={accent}
    style={{height: cardHeight, display: 'flex', flexDirection: 'column', justifyContent: 'center'}}>
    <FittedText text={item.label} width={innerWidth} height={labelHeight}
      fontSize={(pending ? 46 : 30) * unit} minFontSize={18 * unit} lineHeight={1.16}
      style={{color: pending ? white : muted}} />
    <DataValue item={item} width={innerWidth} height={valueHeight} delay={delay} />
    {item.detail ? <FittedText text={item.detail} width={innerWidth} height={detailHeight}
      fontSize={(pending ? 30 : 28) * unit} minFontSize={18 * unit} style={{fontWeight: 500, color: muted}} /> : null}
  </Card>;
};

export const DataAdapter = ({shot}: AdapterProps) => {
  const {unit, contentWidth, contentHeight, headerHeight, bodyHeight, vertical} = useLayout();
  const props = shot.props as DataAdapterProps;
  const items = props.items ?? [];
  const visualization = props.visualization ?? 'cards';
  const columns = vertical && items.length <= 2 ? 1 : items.length === 1 ? 1 : 2;
  const rows = Math.max(1, Math.ceil(items.length / columns));
  const gap = 24 * unit;
  const cardWidth = (contentWidth - (columns - 1) * gap) / columns;
  const availableHeight = contentHeight - headerHeight - (shot.body ? bodyHeight + gap : 0);
  const cardHeight = (availableHeight - (rows - 1) * gap) / rows;
  const innerWidth = cardWidth - 68 * unit;
  const chartWidth = Math.min(contentWidth, 936 * unit);
  const chartHeight = availableHeight;
  return <>
    <SceneHeader shot={shot} />
    {visualization === 'bars' ? <DataBars items={items} accent={shot.accent_color} width={chartWidth} height={chartHeight}
      scaleMax={props.scale_max} unit={props.unit} referenceValue={props.reference_value} /> :
      visualization === 'donuts' ? <DataDonuts items={items} accent={shot.accent_color} width={chartWidth} height={chartHeight} /> :
      <div data-data-grid data-columns={columns} data-rows={rows}
        style={{display: 'grid', gridTemplateColumns: `repeat(${columns}, 1fr)`, gap}}>
        {items.map((item, index) => <DataCard key={`${item.label}-${index}`} item={item} cardHeight={cardHeight}
          innerWidth={innerWidth} delay={index * 4} accent={shot.accent_color} />)}
      </div>}
    <Motion delay={8} style={{marginTop: gap}}><Body text={shot.body} height={bodyHeight} /></Motion>
  </>;
};
