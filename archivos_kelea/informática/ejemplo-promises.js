function fetchNotes() {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve(["Nota 1", "Nota 2", "Nota 3"]);
    }, 1000);
  });
}

async function loadNotes() {
  const notes = await fetchNotes();
  console.log(notes);
}

loadNotes();
