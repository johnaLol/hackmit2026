import {marked} from 'marked';
import descriptionMd from '../markdown/description.md?raw'
import tutorialMd from '../markdown/tutorial.md?raw'
import spectatingMd from '../markdown/spectating.md?raw'

const descriptionElement = document.getElementById('description');
const tutorialElement = document.getElementById('tutorial');
const spectatingElement = document.getElementById('spectating');

const descriptionMdParsed = marked.parse(descriptionMd);
const tutorialMdParsed = marked.parse(tutorialMd);
const spectatingParsed = marked.parse(spectatingMd);

const addDiscordBotButton = document.getElementById('add-to-server-button');
const spectateButton = document.getElementById('spectate-button');

let readMoreToggleFlag = false;

function drawBlocks() {
    descriptionElement!.innerHTML = `
        <h3>Description</h3>
        <p>What is this bot about?</p>
        <span class="material-symbols-outlined">
            question_mark
        </span>
    `;
    tutorialElement!.innerHTML = `
        <h3>Tutorial</h3>
        <p>Overview on how to use bot</p>
        <img>
    `;
    spectatingElement!.innerHTML = `
        <h3>Spectating</h3>
        <p>Learn more about spectating</p>
        <img>
    `;
    addBlockEventListeners();
}


function addBlockEventListeners() {
    descriptionElement?.addEventListener('click', () => {
        createExpansionForMoreInfo(generateMarkdownProse(descriptionMdParsed));
    });
    tutorialElement?.addEventListener('click', () => {
        createExpansionForMoreInfo(generateMarkdownProse(tutorialMdParsed));
    });
    spectatingElement?.addEventListener('click', () => {
        createExpansionForMoreInfo(generateMarkdownProse(spectatingParsed));
    });
}


function generateMarkdownProse(parsedProse: string | Promise<string>) {
    return `
        <div class="expanded-screen-content-container">
            <div class="prose-block">${parsedProse}</div>
        </div>
    `
}


function createExpansionForMoreInfo(paramHTML: string) {
    if (!readMoreToggleFlag) {
        document.body.innerHTML += `
            <div id="expanded-screen-container" class="expanded-screen-container">
                ${paramHTML}
            </div>
        `
        document.getElementById('expanded-screen-container')!.innerHTML += paramHTML;
        readMoreToggleFlag = true;
    } else {
        document.getElementById('expanded-screen-container')?.remove();
        readMoreToggleFlag = false;
    }
}


drawBlocks();
addDiscordBotButton?.addEventListener('click', () => {
    window.location.href = 'https://discord.com/oauth2/authorize?client_id=1550892419837599886&permissions=8&integration_type=0&scope=bot+applications.commands';
})
spectateButton?.addEventListener('click', () => {
    window.location.href = '/spectate';
})
