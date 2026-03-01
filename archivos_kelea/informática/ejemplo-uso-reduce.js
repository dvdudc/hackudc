const items = [
  { name: "React", category: "frontend" },
  { name: "Node", category: "backend" },
  { name: "Vue", category: "frontend" }
];

function groupByCategory(list) {
  return list.reduce((acc, item) => {
    if (!acc[item.category]) {
      acc[item.category] = [];
    }
    acc[item.category].push(item);
    return acc;
  }, {});
}

console.log(groupByCategory(items));
