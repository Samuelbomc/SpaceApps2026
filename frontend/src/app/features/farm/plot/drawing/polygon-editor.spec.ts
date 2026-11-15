import { PolygonEditor } from './polygon-editor';

describe('PolygonEditor', () => {
  it('draws, undoes and only closes with at least three points', () => {
    const e = new PolygonEditor();
    e.add([0, 0]); // ignored while idle
    expect(e.count()).toBe(0);

    e.start();
    e.add([0, 0]);
    e.add([1, 0]);
    expect(e.finish()).toBe(false);
    expect(e.mode()).toBe('drawing');

    e.add([1, 1]);
    e.add([9, 9]);
    e.undo();
    expect(e.vertices()).toEqual([[0, 0], [1, 0], [1, 1]]);
    expect(e.finish()).toBe(true);
    expect(e.mode()).toBe('editing');
    expect(e.closed()).toBe(true);
  });

  it('moves, inserts and removes vertices while editing, never below three', () => {
    const e = new PolygonEditor();
    e.load([[0, 0], [1, 0], [1, 1], [0, 0]]); // closed ring is accepted
    expect(e.count()).toBe(3);

    e.move(1, [2, 0]);
    expect(e.vertices()[1]).toEqual([2, 0]);

    const i = e.insertAfter(1, [2, 1]);
    expect(i).toBe(2);
    expect(e.selected()).toBe(2);
    expect(e.count()).toBe(4);

    e.removeSelected();
    expect(e.count()).toBe(3);
    e.select(0);
    expect(e.canRemoveSelected()).toBe(false);
    e.remove(0);
    expect(e.count()).toBe(3);
  });

  it('flags self-intersection and clears back to idle', () => {
    const e = new PolygonEditor();
    e.load([[0, 0], [1, 1], [1, 0], [0, 1]]);
    expect(e.selfIntersecting()).toBe(true);
    e.clear();
    expect(e.mode()).toBe('idle');
    expect(e.count()).toBe(0);
  });
});
