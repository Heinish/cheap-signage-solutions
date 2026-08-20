let listeners = [];
let idCounter = 0;

export function onToast(fn) {
  listeners.push(fn);
  return () => {
    listeners = listeners.filter((l) => l !== fn);
  };
}

function emit(message, type) {
  const toast = { id: ++idCounter, message, type };
  listeners.forEach((l) => l(toast));
}

export const toast = {
  success: (message) => emit(message, 'success'),
  error: (message) => emit(message, 'error'),
};
