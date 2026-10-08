import {AnimatedBarChart} from '../../components/component-horizontal/remotion-ui/scenes/animated-bar-chart';
import DonutChart from '../../components/component-horizontal/rve/donut-chart';
import {interpolate, useCurrentFrame} from 'remotion';
import type {DataItem} from '../types';
import {Card, FittedText, muted, panel, useLayout, white} from './layout';

export type DataVisualization = 'cards' | 'bars' | 'donuts';

export type DataChartProps = {
  items: DataItem[];
  accent: string;
  width: number;
  height: number;
  scaleMax?: number;
  unit?: string;
  referenceValue?: number;
};

const colors = ['#B7F36B', '#5EEAD4', '#E8B86D', '#93C5FD', '#F9A8D4'];
const revealDurationFrames = 15;

const formatNumber = (value: number) => Number.isInteger(value) ? String(value) : value.toFixed(1).replace(/\.0$/, '');

const requireNumericItems = (items: DataItem[], visualization: DataVisualization) => {
  if (items.length === 0) throw new Error(`Data ${visualization} visualization requires at least one item.`);
  for (const item of items) {
    if (!Number.isFinite(item.numeric_value)) {
      throw new Error(`Data ${visualization} item "${item.label}" requires numeric_value.`);
    }
  }
  return items as Array<DataItem & {numeric_value: number}>;
};

export const DataBars = ({items, accent, width, height, scaleMax, unit = '', referenceValue}: DataChartProps) => {
  const numeric = requireNumericItems(items, 'bars');
  const bars = numeric.map((item, index) => ({
    label: item.label,
    value: item.numeric_value,
    detail: item.detail,
    displayValue: item.value,
    revealFrame: item.reveal_frame,
    color: colors[index % colors.length],
  }));
  const maxValue = scaleMax ?? Math.max(1, ...bars.map((item) => item.value));
  return <div data-data-bars style={{width, height, maxWidth: '100%', margin: '0 auto'}}>
    <AnimatedBarChart
      data={bars}
      maxValue={maxValue}
      valueFormatter={(value) => `${formatNumber(value)}${unit}`}
      accentColor={accent}
      referenceValue={referenceValue}
      referenceLabel={referenceValue === undefined ? undefined : `${formatNumber(referenceValue)}${unit} 基准`}
      viewport={{width, height}}
      embedded
      revealDurationFrames={revealDurationFrames}
    />
  </div>;
};

const DonutMetric = ({item, accent, width, height, index}: {
  item: DataItem & {numeric_value: number};
  accent: string;
  width: number;
  height: number;
  index: number;
}) => {
  const frame = useCurrentFrame();
  const {unit} = useLayout();
  const value = item.numeric_value;
  if (value < 0 || value > 100) throw new Error(`Data donuts item "${item.label}" numeric_value must be between 0 and 100.`);
  const innerWidth = Math.max(1, width - 68 * unit);
  const innerHeight = Math.max(1, height - 68 * unit);
  const labelHeight = Math.max(1, Math.min(74 * unit, innerHeight * 0.24));
  const detailHeight = item.detail ? Math.max(1, Math.min(54 * unit, innerHeight * 0.18)) : 0;
  const gap = Math.min(12 * unit, innerHeight * 0.06);
  const ringHeight = Math.max(1, innerHeight - labelHeight - detailHeight - gap);
  const detailProgress = item.reveal_frame === undefined ? 1 : interpolate(
    frame,
    [item.reveal_frame, item.reveal_frame + revealDurationFrames],
    [0, 1],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
  );
  const detailText = item.reveal_frame !== undefined && detailProgress <= 0 ? '' : item.detail ?? '';
  return <Card accent={accent} style={{height, position: 'relative', background: panel, overflow: 'hidden'}}>
    <FittedText text={item.label} width={innerWidth} height={labelHeight}
      fontSize={36 * unit} minFontSize={20 * unit} preferSingleLine style={{color: white}} />
    {item.detail ? <FittedText text={detailText} width={innerWidth} height={detailHeight}
      fontSize={25 * unit} minFontSize={17 * unit} style={{color: muted, fontWeight: 500, opacity: detailProgress}} /> : null}
    <div data-data-donut={item.label} style={{position: 'relative', height: ringHeight, marginTop: gap}}>
      <DonutChart
        segments={[
          {label: item.label, value, color: colors[index % colors.length]},
          {label: '其他部分', value: 100 - value, color: 'rgba(168,182,203,0.34)'},
        ]}
        title=""
        centerTarget={value}
        centerValueText={item.value}
        centerLabel=""
        layout="portrait"
        viewport={{width: innerWidth, height: ringHeight}}
        embedded
        revealFrame={item.reveal_frame}
        revealDurationFrames={revealDurationFrames}
      />
    </div>
  </Card>;
};

export const DataDonuts = ({items, accent, width, height}: DataChartProps) => {
  const {unit, vertical} = useLayout();
  if (items.length > 2) throw new Error('Data donuts visualization supports at most 2 items.');
  const donuts = requireNumericItems(items, 'donuts');
  const gap = 24 * unit;
  const columns = vertical ? 1 : Math.max(1, donuts.length);
  const rows = Math.max(1, Math.ceil(donuts.length / columns));
  const cardWidth = (width - (columns - 1) * gap) / columns;
  const cardHeight = (height - (rows - 1) * gap) / rows;
  return <div data-data-donuts data-donut-count={donuts.length}
    style={{display: 'grid', gridTemplateColumns: `repeat(${columns}, 1fr)`, gap, width, maxWidth: '100%', margin: '0 auto'}}>
    {donuts.map((item, index) => <DonutMetric key={`${item.label}-${index}`} item={item} accent={accent}
      width={cardWidth} height={cardHeight} index={index} />)}
  </div>;
};
