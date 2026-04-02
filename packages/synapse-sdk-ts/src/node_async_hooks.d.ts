declare module "node:async_hooks" {
  class AsyncLocalStorage<T> {
    run<R>(store: T, callback: (...args: any[]) => R, ...args: any[]): R;
    getStore(): T | undefined;
  }

  export { AsyncLocalStorage };
}
