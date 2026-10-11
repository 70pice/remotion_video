export const richMaterialGeometry = Object.freeze({
  material: {x: 56, y: 64, width: 968, height: 900},
  title: {x: 64, y: 1000, width: 952, height: 190},
  support: {x: 64, y: 1210, width: 952, height: 430},
  emphasis: {x: 64, y: 1700, width: 952, height: 100},
  identity: {x: 70, y: 1840, width: 940, height: 42},
});

export const richMaterialBoxesDoNotOverlap = (): boolean => {
  const boxes = [richMaterialGeometry.material, richMaterialGeometry.title,
    richMaterialGeometry.support, richMaterialGeometry.emphasis, richMaterialGeometry.identity];
  return boxes.every((box, index) => index === 0 || boxes[index - 1].y + boxes[index - 1].height <= box.y);
};
