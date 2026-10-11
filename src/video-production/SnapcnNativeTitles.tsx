import {AbsoluteFill} from 'remotion';
import {
  AnswerHighlight, AnswerStream, KaraokeCaptions, PromptSend, SearchTyping,
  TextBuild, TextHighlight, TextReveal, TextRewrite, TextSwap, WordCaptions, WordFlip,
} from '../components/component-horizontal/snapcn';
import {productionFont} from './adapters/layout';
import type {ShotLayer} from '../../contracts/generated/models';

// These bind the author's real, prop-driven components, never the demo entrypoints.
export const snapcnNativeTitleIds = [
  'Snapcn-TextReveal', 'Snapcn-TextBuild', 'Snapcn-TextHighlight', 'Snapcn-TextRewrite',
  'Snapcn-TextSwap', 'Snapcn-WordFlip', 'Snapcn-WordCaptions', 'Snapcn-KaraokeCaptions',
  'Snapcn-SearchTyping', 'Snapcn-PromptSend', 'Snapcn-AnswerStream', 'Snapcn-AnswerHighlight',
] as const;

export const SnapcnNativeTitle = ({layer, tutorial = false, textOnly = false, richTitle = false}: {layer: ShotLayer; tutorial?: boolean; textOnly?: boolean; richTitle?: boolean}) => {
  const props = layer.props;
  const supplied = (name: string, fallback: string) => typeof props[name] === 'string' ? props[name] as string : fallback;
  const items = Array.isArray(props.items) ? props.items.filter((item): item is string => typeof item === 'string') : [];
  const title = layer.title;
  const longest = Math.max([...title].length, ...['from_text', 'to_text'].map((key) => [...supplied(key, '')].length),
    ...items.map((item) => [...item].length), [...supplied('before', '') + supplied('highlight', title) + supplied('after', '')].length);
  const fontSize = Math.min(richTitle ? 92 : textOnly ? 76 : 64,
    (richTitle && layer.component_id === 'Snapcn-TextHighlight' ? 720 : richTitle ? 920 : 850)
      / Math.max(richTitle ? 9 : textOnly ? 10 : 14, longest));
  const ink = '#F4F7FC';
  const shared = {fontFamily: productionFont, mode: 'dark' as const,
    theme: textOnly ? {background: 'transparent', foreground: ink} : undefined};
  const accent = layer.accent_color;
  let content;
  switch (layer.component_id) {
    case 'Snapcn-TextReveal':
      content = <TextReveal text={title} fontSize={tutorial ? Math.min(72, 860 / Math.max(1, longest)) : fontSize} initialScale={tutorial ? 1 : 1.3}
        color={ink} introDuration={tutorial ? 3 : 8} holdDuration={tutorial ? 1 : 8}
        recedeDuration={tutorial ? 1 : 10} assembleDuration={tutorial ? 1 : 12}
        pushScale={tutorial ? 1 : 1.06} wordDelay={tutorial ? 0 : 7} wordStagger={tutorial ? 0 : 4}
        wordDuration={tutorial ? 3 : 14} wordFade={tutorial ? 3 : 2} wordPush={tutorial ? 0 : 0.5} {...shared} />;
      break;
    case 'Snapcn-TextBuild':
      content = <TextBuild text={items.length ? items.join(' ') : title} axis={items.length > 1 ? 'y' : 'x'} fontSize={fontSize}
        color={ink} firstDuration={10} pushDuration={12} {...shared} />;
      break;
    case 'Snapcn-TextHighlight':
      content = <TextHighlight before={supplied('before', '')} highlight={supplied('highlight', title)}
        after={supplied('after', '')} preset={textOnly ? 'underline' : 'marker'} baseColor={ink} accentColor={accent}
        fontSize={fontSize} startAt={6} drawDuration={16} {...shared} />;
      break;
    case 'Snapcn-TextRewrite':
      content = <TextRewrite headline={supplied('from_text', title)} keep={0}
        append={supplied('to_text', layer.body || title)} markSize={0} fontSize={fontSize}
        wordAt={0.05} wordStagger={0.03} cutAt={0.4} zoom={1} dragAt={0.45}
        dragDuration={0.2} eraseAt={0.7} eraseDuration={0.15} rewriteAt={0.9}
        rewriteDuration={0.5} deselectAt={1.6} accentColor={accent} glow={false} {...shared} />;
      break;
    case 'Snapcn-TextSwap':
      content = <TextSwap fromText={supplied('from_text', title)}
        toText={supplied('to_text', layer.body || title)} fontSize={fontSize}
        exitDuration={12} enterDuration={15} color={ink} {...shared} />;
      break;
    case 'Snapcn-WordFlip':
      content = <WordFlip prefix="" suffix="" words={items.length ? items : [title, layer.body || title]}
        fontSize={fontSize} typeStart={0} cps={40} pause={10} cycle={30} loop={false}
        gradient={[accent, ink]} {...shared} />;
      break;
    case 'Snapcn-WordCaptions':
      // A single supplied callout, not a second transcript or fabricated word alignment.
      content = <WordCaptions words={[{text: title, startFrame: 0, endFrame: layer.end_frame - layer.start_frame}]}
        fontSize={fontSize} groupSize={1} maxWidth={880} aspect="16:9" textColor={ink}
        accentColor={accent} pillColor="#07101F" {...shared} />;
      break;
    case 'Snapcn-KaraokeCaptions':
      content = <KaraokeCaptions text={title} emphasize={supplied('highlight', title)}
        fontSize={fontSize} aspect="landscape" accentColor={accent} pill={true} {...shared} />;
      break;
    case 'Snapcn-SearchTyping':
      content = <SearchTyping text={title} charsPerSecond={30} startDelay={0.05}
        fieldHeight={richTitle ? 0.58 : 0.3} frontVisible={richTitle ? 0.9 : 0.95} dolly={1} recedeDuration={0}
        fontFamily={productionFont} mode="dark" />;
      break;
    case 'Snapcn-PromptSend':
      content = <PromptSend text={title} placeholder="机制示意" chips={items}
        width={760} fontSize={40} chipFontSize={28} revealAt={0} revealDuration={0.2}
        {...shared} />;
      break;
    case 'Snapcn-AnswerStream':
      content = <AnswerStream question={title} answer={layer.body || title} headline=""
        cards={[]} model="机制示意" commitAt={0.15} cutAt={0.3} pullbackAt={0.35}
        pullbackDuration={0.5} macroZoom={1} pullbackFrom={1} wordsPerSecond={12}
        accentColor={accent} productionCompact {...shared} />;
      break;
    case 'Snapcn-AnswerHighlight':
      content = <AnswerHighlight question={richTitle && layer.role === 'emphasis' ? '' : title}
        answer={richTitle && layer.role === 'emphasis' ? title : layer.body || title}
        statement={richTitle && layer.role === 'emphasis' ? title : layer.body || title}
        word={richTitle && layer.role === 'emphasis' ? '' : layer.body || title} questionHold={0.2}
        compactCallout={richTitle && layer.role === 'emphasis'}
        compactAnswerFontSize={richTitle ? Math.min(68, 840 / Math.max(12, [...title].length)) : undefined}
        compactQuestionFontSize={richTitle ? 44 : undefined}
        compactWidthRatio={richTitle ? 0.94 : undefined}
        beforeDrag={0.1} beforeWord={0.15} wordStep={0.08} dragStep={0.08}
        accentColor={accent} productionCompact {...shared} />;
      break;
    default:
      throw new Error(`No native Snapcn title binding: ${layer.component_id}`);
  }
  return <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center',
    background: tutorial || textOnly ? 'transparent' : '#07101F', fontFamily: productionFont, borderRadius: 24, overflow: 'hidden'}}>
    {content}
    {!(richTitle && layer.role === 'emphasis') && ['Snapcn-PromptSend', 'Snapcn-AnswerStream', 'Snapcn-AnswerHighlight'].includes(layer.component_id)
      ? <div style={{position: 'absolute', top: 12, left: 18, color: '#A8B6CB', fontSize: 22}}>机制示意</div> : null}
  </AbsoluteFill>;
};
