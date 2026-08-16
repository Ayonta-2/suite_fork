// the worker decides asset ownership per client, so the page has to say when it is slides
export const postToServiceWorker = (message: string) => {
  navigator.serviceWorker?.controller?.postMessage(message)
}
