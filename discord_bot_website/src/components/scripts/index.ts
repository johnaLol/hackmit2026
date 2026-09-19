import {marked} from 'marked';
import aboutMd from '../markdown/about.md?raw'
import tutorialMd from '../markdown/tutorial.md?raw'
import somethingMd from '../markdown/something.md?raw'

const aboutElement = document.getElementById('about');
const tutorialElement = document.getElementById('tutorial');
const otherElement = document.getElementById('something-else');

const aboutMdParsed = marked.parse(aboutMd);
const tutorialMdParsed = marked.parse(tutorialMd);
const somethingMdParsed = marked.parse(somethingMd);

const addDiscordBotButton = document.getElementById('add-to-server-button');

function drawBlocks() {
    aboutElement!.innerHTML = `
        <h3>Description</h3>
        <p>Learn about the bot</p>
    `;
    tutorialElement!.innerHTML = `
        <h3>Tutorial</h3>
        <p>Brief overview on how to use</p>
    `;
    otherElement!.innerHTML = `
        <h3>About Us</h3>
        <p>Learn more about the devs</p>
    `;
    addBlockEventListeners();
}


function addBlockEventListeners() {
    aboutElement?.addEventListener('click', () => {
        darkenScreen();
    });
    aboutElement?.addEventListener('click', () => {
        darkenScreen();
    });
    aboutElement?.addEventListener('click', () => {
        darkenScreen();
    });
}


function darkenScreen() {
    console.log('hi');
}


drawBlocks();
addDiscordBotButton?.addEventListener('click', () => {
    window.location.href = 'https://discord.com/oauth2/authorize?client_id=1550892419837599886&permissions=8&integration_type=0&scope=bot+applications.commands';
})
