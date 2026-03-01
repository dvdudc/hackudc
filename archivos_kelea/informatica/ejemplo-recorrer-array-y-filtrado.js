const users = [
  { id: 1, name: "Ana", active: true },
  { id: 2, name: "Luis", active: false },
  { id: 3, name: "Marta", active: true }
];

function getActiveUsers(userList) {
  return userList.filter(user => user.active);
}

const activeUsers = getActiveUsers(users);
console.log(activeUsers);
