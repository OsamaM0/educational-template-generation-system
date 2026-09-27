/* global use, db */
// MongoDB Playground
// Use Ctrl+Space inside a snippet or a string literal to trigger completions.

// The current database to use.
use("ai");

// Find a document in a collection.
db.getCollection("questions").findOne({
    document_idx: '152225'
});
