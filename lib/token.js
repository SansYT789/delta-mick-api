const jwt = require("jsonwebtoken");

const SECRET = process.env.JWT_SECRET;

function createToken(id) {
    return jwt.sign(
        { id },
        SECRET,
        { expiresIn: "60s" }
    );
}

function verifyToken(token) {
    try {
        return jwt.verify(token, SECRET);
    } catch {
        return null;
    }
}

module.exports = {
    createToken,
    verifyToken
};