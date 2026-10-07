import { describe, it, expect } from "vitest";
import { ancestors, buildTree, byName, findNode, isUnder, normalizePath, parseParents, pathLabel } from "../parents";

describe("parent paths", () => {
  it("normalizes and labels paths", () => {
    expect(normalizePath(" 課程 / 第一組 ")).toBe("課程/第一組");
    expect(parseParents("課程/第一組, 課程／第二組")).toEqual(["課程/第一組", "課程/第二組"]);
    expect(pathLabel("課程/第一組")).toBe("課程 › 第一組");
    expect(pathLabel("課程/第一組/A", "課程")).toBe("第一組 › A");
    expect(ancestors("a/b/c")).toEqual(["a", "a/b", "a/b/c"]);
    expect(isUnder("a/b", "a")).toBe(true);
    expect(isUnder("ab", "a")).toBe(false);
  });

  it("sorts Chinese group numbers as numbers", () => {
    const groups = ["第十二組", "第二組", "第一組", "第十組", "第三組"];
    expect([...groups].sort(byName)).toEqual(["第一組", "第二組", "第三組", "第十組", "第十二組"]);
  });

  it("builds a tree with same names under different groups", () => {
    const cats = [
      { id: 1, name: "人", supercategories: ["課程/第一組"] },
      { id: 2, name: "人", supercategories: ["課程/第二組"] },
      { id: 3, name: "車", supercategories: ["課程/第一組"] },
      { id: 4, name: "樹", supercategories: [] }
    ];
    const tree = buildTree(cats);
    expect(tree.children.map(n => n.name)).toEqual(["課程"]);
    const course = findNode(tree, "課程");
    expect(course.all.map(c => c.id)).toEqual([1, 2, 3]);
    expect(course.items).toEqual([]);
    expect(course.children.map(n => n.name)).toEqual(["第一組", "第二組"]);
    expect(findNode(tree, "課程/第一組").items.map(c => c.id)).toEqual([1, 3]);
    expect(findNode(tree, "nope")).toBe(null);
  });
});
