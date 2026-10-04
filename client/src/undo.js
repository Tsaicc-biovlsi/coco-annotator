import axios from "axios";

export default class UndoAction {
  constructor({ name, action, func, args }) {
    this.name = name;
    this.action = action;
    this.func = func;
    this.args = args;
  }

  undo() {
    return this.func(this.args);
  }
}

/**
 * Undo for deleted annotations: restore them on the server (deleting only
 * marks them as deleted) and put them back in their category lists, with
 * the shape they had when they were deleted.
 * @param {Array<{category: Object, data: Object}>} snapshots
 */
export function restoreAnnotations(snapshots) {
  return Promise.all(
    snapshots.map(({ data }) => axios.post(`/api/undo/?id=${data.id}&instance=annotation`))
  ).then(() => {
    snapshots.forEach(({ category, data }) => {
      if (!category.annotations.some(a => a.id === data.id)) {
        category.annotations.push(data);
      }
    });
  });
}
