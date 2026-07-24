const MEMES = [
    {
        id: 1,
        file: "drake.png",
        answer: [
            "drake",
            "drake hotline bling"
        ],
        reward: 100
    },
    {
        id: 2,
        file: "doge.png",
        answer: [
            "doge"
        ],
        reward: 80
    }
];

function randomMeme() {
    return MEMES[
        Math.floor(Math.random() * MEMES.length)
    ];
}

module.exports = {
    randomMeme,
    MEMES
};