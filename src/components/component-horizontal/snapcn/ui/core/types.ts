// Vendored from snapcndev/snapcn at 4399d249002afae506497cc90ac3f064e189127d. MIT; see licenses/community/snapcn.
export interface Step<S extends string = string> {
  at: number;
  state: S;
  duration?: number;
}
