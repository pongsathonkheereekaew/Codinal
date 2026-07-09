import { EventEmitter } from 'node:events';

export const bus = new EventEmitter();
bus.setMaxListeners(50);

export const changed = (reason) => bus.emit('changed', reason);
export const notify = (text, topic) => bus.emit('notify', { text, topic });
