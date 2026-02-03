import { useEffect, type RefObject } from 'react';

type KeyboardShortcutHandlers = {
  onSave?: () => boolean | Promise<boolean>;
  onUndo?: () => void;
  onRedo?: () => void;
  onDelete?: () => boolean;
};

type KeyboardShortcutOptions = {
  enabled?: boolean;
  containerRef?: RefObject<HTMLElement>;
};

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName.toLowerCase();
  return tag === 'input' || tag === 'textarea' || target.isContentEditable;
}

export function useKeyboardShortcuts(
  handlers: KeyboardShortcutHandlers,
  options: KeyboardShortcutOptions = {}
) {
  const { enabled = true, containerRef } = options;

  useEffect(() => {
    if (!enabled) return;

    const element = containerRef?.current;
    const target = element ?? window;

    const onKeyDown: EventListener = (evt) => {
      if (!(evt instanceof KeyboardEvent)) return;
      const e = evt;
      const hasMod = e.ctrlKey || e.metaKey;

      if (hasMod && e.key.toLowerCase() === 's') {
        e.preventDefault();
        void handlers.onSave?.();
        return;
      }

      if (hasMod && e.key.toLowerCase() === 'z') {
        e.preventDefault();
        if (e.shiftKey) {
          handlers.onRedo?.();
        } else {
          handlers.onUndo?.();
        }
        return;
      }

      if (hasMod && e.key.toLowerCase() === 'y') {
        e.preventDefault();
        handlers.onRedo?.();
        return;
      }

      if ((e.key === 'Delete' || e.key === 'Backspace') && !isEditableTarget(e.target)) {
        const didDelete = handlers.onDelete?.();
        if (didDelete) {
          e.preventDefault();
        }
      }
    };

    target.addEventListener('keydown', onKeyDown);
    return () => {
      target.removeEventListener('keydown', onKeyDown);
    };
  }, [enabled, containerRef, handlers]);
}
