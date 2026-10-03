import {config} from '@remotion/eslint-config-flat';
// Keep byte-preserved upstream cards intact; typecheck and render verify them.
export default [...config, {ignores: ['src/components/component-horizontal/video-talkcraft/cards/**']}];
