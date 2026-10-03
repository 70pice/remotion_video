// Vendored from remocn @ 8ae853e4c08108105684d4b8cac7f22400840d2a: registry/remocn-ui/core/types.ts
export interface Step<S extends string = string> {
  at: number;
  state: S;
  duration?: number;
}
