export type CommunityMaterialSurface =
  | 'card'
  | 'data'
  | 'device'
  | 'gallery'
  | 'motion'
  | 'pip'
  | 'reveal'
  | 'text'
  | 'workspace';

export const communityMaterialSurfaceName: Record<CommunityMaterialSurface, string> = {
  card: 'material card',
  data: 'data panel',
  device: 'device frame',
  gallery: 'gallery wall',
  motion: 'motion canvas',
  pip: 'picture-in-picture',
  reveal: 'reveal mask',
  text: 'type frame',
  workspace: 'workspace panel',
};

const matches = (value: string, patterns: RegExp[]) => patterns.some((pattern) => pattern.test(value));

export const communityMaterialSurfaceForComponentId = (componentId: string): CommunityMaterialSurface => {
  const id = componentId.toLowerCase();
  if (matches(id, [
    /terminal/, /code/, /cursor/, /cli/, /command/, /console/, /debug/, /trace/, /log/,
    /editor/, /diff/, /deploy/, /workflow/, /kanban/, /agent/, /chat/, /thread/,
    /prompt/, /search/,
  ])) return 'workspace';
  if (matches(id, [
    /device/, /mockup/, /phone/, /iphone/, /android/, /laptop/, /screen/, /browser/,
    /window/, /interface/, /dashboard/, /recording/, /product/, /app/,
  ])) return 'device';
  if (matches(id, [
    /picture-in-picture/, /pictureinpicture/, /pip/, /social/, /reel/, /clip/, /short/, /story/, /portrait/,
    /tiktok/, /vertical/,
  ])) return 'pip';
  if (matches(id, [
    /gallery/, /masonry/, /carousel/, /photo/, /image/, /polaroid/, /moodboard/, /grid/,
    /stack/, /ken-burns/, /kenburns/,
  ])) return 'gallery';
  if (matches(id, [
    /chart/, /kpi/, /metric/, /stat/, /counter/, /progress/, /rank/, /race/, /bar/,
    /line/, /pie/, /donut/, /candlestick/, /ohlc/, /waterfall/, /data/, /ticker/, /number/,
  ])) return 'data';
  if (matches(id, [
    /text/, /title/, /word/, /type/, /quote/, /caption/, /keyword/, /headline/,
    /lower-third/, /lowerthird/, /label/, /badge/, /slab/, /split/, /character/,
    /line-by-line/, /tracking/,
  ])) return 'text';
  if (matches(id, [
    /reveal/, /wipe/, /iris/, /reticle/, /mask/, /scan/, /spotlight/, /clock/,
    /transition/, /zoom/, /punch/, /impact/, /morph/, /lock-on/,
  ])) return 'reveal';
  if (matches(id, [
    /wave/, /audio/, /path/, /draw/, /pencil/, /aurora/, /glow/, /particle/, /shape/,
    /orbit/, /loop/, /cycle/,
  ])) return 'motion';
  return 'card';
};
