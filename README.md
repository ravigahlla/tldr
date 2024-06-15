# Project: tldr
A GPT-powered summarizer, to deal with Stratechery's daily volume of emails

**Problem**: [Stratechery](https://stratechery.com/) is a daily newsletter for technology that can contain valuable content, but the 
daily emails add up as unread after at least a week

**Solution**: Use OpenAI's API to summarize the daily newsletters, saving you time

*Program Design*

See [tldr-v1-workflow](docs%2Ftldr-v1-workflow.pdf) for visual

1. From an external server, check daily for emails from Stratechery
2. Summarize the email with [OpenAI's API](https://platform.openai.com/overview)
3. Send the summary back to my email, along with:
4. An executive summary, keywords, and then the original email

REQs:
- a paid account with OpenAI
- a gmail account [with your app pass key setup](https://support.google.com/mail/answer/185833?hl=en)
- you can set this up on your local, but an external server (I used a Raspberry Pi)

Setup
1. check out the repo, go to the project directory
2. you need to create your own .config file, containing your credentials (e.g., gmail app pass) in JSON format
3. run 'sudo chmod 600 .config' to give yourself permission to read from the file
4. run 'install .' to run setup.py, and install the right dependencies
5. run 'python3 src/main.py'


***TODO***
- ~~need to handling token limits (4096)~~
- ~~setup this script on a separate server (or a Raspberry Pi)~~
- ~~set a cron job to either run at a specific time, or ping my email and send me a summary~~
- ~~deal with rich-content email (embedded video, audio) summarization~~
- ~~split up methods into different related files (or create a class to handle)~~
- create a test flag, to reference variables with various test values (and then a "PROD" state, which will
make it ready for public-use), and cut down on the OpenAI cost by using smaller test articles
- better handle error handling in the try catch code properly (openai.error doesn't exist, so need to find updated version)
- make this server interactive: I can email back a reply, and then get a response, if I want to dig deeper
- setup another email handle (e.g., 'summarizerbot@')?
- be LLM agnostic (support for OpenAI, Gemini, or a combination of all)
- can asynchronous summarization be used?