import {Img, interpolate, staticFile, useCurrentFrame} from 'remotion';
import type {DataItem, Highlight, StepItem} from '../types';
import {Body, Card, FittedText, Motion, SceneHeader, clamp, contrastingInk, gentleZoom, muted, useLayout, white} from './layout';
import type {AdapterProps} from './layout';

export const TitleAdapter = ({shot}: AdapterProps) => {
  const {unit, contentWidth, contentHeight} = useLayout();
  const eyebrow = shot.props.eyebrow as string | undefined;
  const textBudget = contentHeight - (eyebrow ? 100 : 0) * unit - 93 * unit;
  const titleHeight = textBudget * (shot.body ? 0.59 : 0.98);
  const bodyHeight = textBudget * 0.41;
  return <div style={{height: contentHeight, display: 'flex', flexDirection: 'column', justifyContent: 'center'}}>
    {eyebrow ? <Motion><div style={{fontSize: 28 * unit, color: muted, marginBottom: 50 * unit, letterSpacing: 2 * unit}}>{eyebrow}</div></Motion> : null}
    <Motion><FittedText text={shot.title} width={contentWidth} height={titleHeight}
      fontSize={126 * unit} minFontSize={42 * unit} lineHeight={1.22} /></Motion>
    <Motion delay={5}><div style={{height: 9 * unit, width: 136 * unit, background: shot.accent_color, margin: `${42 * unit}px 0`}} />
      <Body text={shot.body} height={bodyHeight} />
    </Motion>
  </div>;
};

export const KeywordAdapter = ({shot}: AdapterProps) => {
  const frame = useCurrentFrame();
  const {unit, contentWidth, contentHeight, vertical, durationInFrames} = useLayout();
  const keyword = (shot.props.keyword as string | undefined) ?? shot.title;
  const reveal = interpolate(frame, [0, Math.max(1, Math.min(14, durationInFrames * 0.25))], [0, 1], clamp);
  const contextHeight = (vertical ? 80 : 60) * unit;
  const textBudget = contentHeight - contextHeight - 156 * unit;
  return <div style={{height: contentHeight, display: 'flex', flexDirection: 'column', justifyContent: 'center'}}>
    <Motion style={{marginBottom: 40 * unit}}><FittedText text={keyword === shot.title ? '核心观点' : shot.title}
      width={contentWidth} height={contextHeight} fontSize={30 * unit} minFontSize={18 * unit} style={{color: muted}} /></Motion>
    <Motion delay={3}><div style={{position: 'relative', padding: `${32 * unit}px ${28 * unit}px`, marginLeft: -28 * unit}}>
      <div style={{position: 'absolute', inset: 0, background: shot.accent_color, transform: `scaleX(${reveal})`, transformOrigin: 'left', borderRadius: 12 * unit}} />
      <FittedText text={keyword} width={contentWidth} height={textBudget * (shot.body ? 0.58 : 0.98)}
        fontSize={128 * unit} minFontSize={40 * unit} lineHeight={1.18} style={{position: 'relative', color: contrastingInk(shot.accent_color)}} />
    </div></Motion>
    <Motion delay={8} style={{marginTop: 52 * unit}}><Body text={shot.body} height={textBudget * 0.42} /></Motion>
  </div>;
};

const ImageCard = ({shot, focus, durationInFrames}: AdapterProps & {focus: boolean}) => {
  const frame = useCurrentFrame();
  const {unit, contentWidth, contentHeight, headerHeight, bodyHeight} = useLayout();
  const mediaHeight = contentHeight - headerHeight - bodyHeight - 58 * unit;
  const highlight = shot.props.highlight as Highlight | undefined;
  const focalX = (shot.props.focal_x as number | undefined) ?? 0.5;
  const focalY = (shot.props.focal_y as number | undefined) ?? 0.5;
  return <>
    <SceneHeader shot={shot} />
    <Motion delay={4}>
      <Card accent={shot.accent_color} style={{padding: 14 * unit, overflow: 'hidden'}}>
        <div style={{position: 'relative', height: mediaHeight, overflow: 'hidden', borderRadius: 16 * unit,
          display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#F1F3F7'}}>
          {focus ? <Img src={staticFile(shot.asset_src!)} style={{width: '100%', height: '100%', objectFit: 'cover',
            objectPosition: `${focalX * 100}% ${focalY * 100}%`,
            transform: `scale(${gentleZoom(frame, durationInFrames)})`,
            transformOrigin: `${focalX * 100}% ${focalY * 100}%`}} /> :
            <div style={{position: 'relative', display: 'inline-flex'}}>
              <Img src={staticFile(shot.asset_src!)} style={{display: 'block', width: 'auto', height: 'auto',
                maxWidth: contentWidth - 30 * unit, maxHeight: mediaHeight}} />
              {highlight ? <div style={{position: 'absolute', left: `${highlight.x * 100}%`, top: `${highlight.y * 100}%`,
                width: `${highlight.width * 100}%`, height: `${highlight.height * 100}%`, boxSizing: 'border-box',
                border: `${4 * unit}px solid ${shot.accent_color}`, background: shot.accent_color + '18',
                opacity: interpolate(frame, [0, Math.max(1, Math.min(20, durationInFrames * 0.3))], [0, 1], clamp)}} /> : null}
            </div>}
        </div>
      </Card>
    </Motion>
    <Motion delay={7} style={{marginTop: 24 * unit}}><Body text={shot.body} height={bodyHeight} /></Motion>
  </>;
};

export const EvidenceAdapter = (props: AdapterProps) => <ImageCard {...props} focus={false} />;
export const ImageFocusAdapter = (props: AdapterProps) => <ImageCard {...props} focus />;

export const ComparisonAdapter = ({shot}: AdapterProps) => {
  const {unit, contentWidth, contentHeight, vertical, headerHeight, bodyHeight} = useLayout();
  const cardWidth = vertical ? contentWidth : (contentWidth - 24 * unit) / 2;
  const availableHeight = contentHeight - headerHeight - (shot.body ? bodyHeight + 24 * unit : 0);
  const cardHeight = (availableHeight - (vertical ? 24 * unit : 0)) / (vertical ? 2 : 1);
  const sides = [
    {title: shot.props.left_title as string, body: shot.props.left_body as string},
    {title: shot.props.right_title as string, body: shot.props.right_body as string},
  ];
  return <>
    <SceneHeader shot={shot} />
    <div style={{display: 'flex', flexDirection: vertical ? 'column' : 'row', gap: 24 * unit}}>
      {sides.map((side, index) => <Motion key={index} delay={index * 5} style={{width: cardWidth}}>
        <Card accent={index === 1 ? shot.accent_color : undefined} style={{height: cardHeight}}>
          <div style={{fontSize: 24 * unit, color: muted, marginBottom: 20 * unit}}>{index === 0 ? 'A' : 'B'}</div>
          <FittedText text={side.title} width={cardWidth - 68 * unit} height={(cardHeight - 146 * unit) * 0.4}
            fontSize={58 * unit} minFontSize={26 * unit} />
          <Body text={side.body} width={cardWidth - 68 * unit} height={(cardHeight - 146 * unit) * 0.6} style={{marginTop: 24 * unit}} />
        </Card>
      </Motion>)}
    </div>
    {shot.body ? <Motion delay={10} style={{marginTop: 24 * unit}}><Body text={shot.body} height={bodyHeight} /></Motion> : null}
  </>;
};

export const DataAdapter = ({shot}: AdapterProps) => {
  const {unit, contentWidth, contentHeight, headerHeight, bodyHeight} = useLayout();
  const items = shot.props.items as DataItem[];
  const columns = items.length === 1 ? 1 : 2;
  const rows = Math.ceil(items.length / columns);
  const cardWidth = (contentWidth - (columns - 1) * 24 * unit) / columns;
  const availableHeight = contentHeight - headerHeight - (shot.body ? bodyHeight + 24 * unit : 0);
  const cardHeight = (availableHeight - (rows - 1) * 24 * unit) / rows;
  return <>
    <SceneHeader shot={shot} />
    <div style={{display: 'grid', gridTemplateColumns: `repeat(${columns}, 1fr)`, gap: 24 * unit}}>
      {items.map((item, index) => <Motion key={index} delay={index * 4}>
        <Card accent={shot.accent_color} style={{height: cardHeight, display: 'flex', flexDirection: 'column', justifyContent: 'center'}}>
          <FittedText text={item.label} width={cardWidth - 68 * unit} height={(cardHeight - 92 * unit) * 0.27}
            fontSize={30 * unit} minFontSize={18 * unit} style={{color: muted}} />
          <FittedText text={item.value} width={cardWidth - 68 * unit} height={(cardHeight - 92 * unit) * (item.detail ? 0.43 : 0.7)}
            fontSize={96 * unit} minFontSize={24 * unit} lineHeight={1.12} style={{margin: `${12 * unit}px 0`, color: white}} />
          {item.detail ? <FittedText text={item.detail} width={cardWidth - 68 * unit} height={(cardHeight - 92 * unit) * 0.3}
            fontSize={28 * unit} minFontSize={18 * unit} style={{fontWeight: 500, color: muted}} /> : null}
        </Card>
      </Motion>)}
    </div>
    <Motion delay={8} style={{marginTop: 24 * unit}}><Body text={shot.body} height={bodyHeight} /></Motion>
  </>;
};

export const StepsAdapter = ({shot}: AdapterProps) => {
  const {unit, contentWidth, contentHeight, headerHeight, bodyHeight, vertical} = useLayout();
  const items = shot.props.items as StepItem[];
  const columns = !vertical && items.length > 2 ? 2 : 1;
  const rows = Math.ceil(items.length / columns);
  const cardWidth = (contentWidth - (columns - 1) * 18 * unit) / columns;
  const availableHeight = contentHeight - headerHeight - (shot.body ? bodyHeight + 24 * unit : 0);
  const cardHeight = (availableHeight - (rows - 1) * 18 * unit) / rows;
  return <>
    <SceneHeader shot={shot} />
    <div style={{display: 'grid', gridTemplateColumns: `repeat(${columns}, 1fr)`, gap: 18 * unit}}>
      {items.map((item, index) => <Motion key={index} delay={index * 4}>
        <Card style={{height: cardHeight, display: 'flex', alignItems: 'center', gap: 30 * unit, padding: 26 * unit}}>
          <div style={{alignSelf: 'center', flexShrink: 0, width: 66 * unit, height: 66 * unit, borderRadius: 18 * unit,
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 30 * unit,
            background: shot.accent_color, color: contrastingInk(shot.accent_color), fontWeight: 800}}>{index + 1}</div>
          <div style={{flex: 1, minWidth: 0}}>
            <FittedText text={item.title} width={cardWidth - 154 * unit} height={(cardHeight - 66 * unit) * (item.body ? 0.5 : 0.9)}
              fontSize={45 * unit} minFontSize={24 * unit} />
            {item.body ? <Body text={item.body} width={cardWidth - 154 * unit} height={(cardHeight - 66 * unit) * 0.5} style={{marginTop: 14 * unit}} /> : null}
          </div>
        </Card>
      </Motion>)}
    </div>
    <Motion delay={8} style={{marginTop: 24 * unit}}><Body text={shot.body} height={bodyHeight} /></Motion>
  </>;
};

export const ConclusionAdapter = ({shot}: AdapterProps) => {
  const {unit, contentWidth, contentHeight, vertical} = useLayout();
  const callToAction = shot.props.call_to_action as string | undefined;
  const actionHeight = (vertical ? 150 : 80) * unit;
  const cardHeight = contentHeight - 70 * unit - (callToAction ? actionHeight + 40 * unit : 0);
  const textHeight = cardHeight - 161 * unit;
  return <div style={{height: contentHeight, display: 'flex', flexDirection: 'column', justifyContent: 'center'}}>
    <Motion><div style={{fontSize: 28 * unit, color: muted, marginBottom: 32 * unit}}>最后记住</div></Motion>
    <Motion delay={3}><Card accent={shot.accent_color} style={{padding: 48 * unit}}>
      <FittedText text={shot.title} width={contentWidth - 96 * unit} height={textHeight * (shot.body ? 0.55 : 0.98)}
        fontSize={94 * unit} minFontSize={34 * unit} lineHeight={1.24} />
      <div style={{height: 5 * unit, width: 90 * unit, background: shot.accent_color, margin: `${30 * unit}px 0`}} />
      <Body text={shot.body} width={contentWidth - 96 * unit} height={textHeight * 0.45} />
    </Card></Motion>
    {callToAction ? <Motion delay={10} style={{marginTop: 40 * unit}}><FittedText text={callToAction}
      width={contentWidth} height={actionHeight} fontSize={36 * unit} style={{textAlign: 'center', color: muted}} /></Motion> : null}
  </div>;
};
