# stratecheryGPT
A summarizer to deal with Stratechery's incessant daily emails

**Problem**: [Stratechery](https://stratechery.com/) is a daily newsletter for technology that can contain
valuable content, but it is too verbose, and the inability to digest these daily newsletters adds up, causing valuable
information to be missed (investment opportunities, strategic shifts)

**Solution**: Use OpenAI's GPT API in order to summarize the daily email newsletters according to a prompt designed to 
extract the most useful information

*Program Design*
See [stratecheryGPT-v1-workflow](docs%2FstratecheryGPT-v1-workflow.pdf) for visual

1. Have a daily cron job running from an external server, looking for emails from email@stratechery.com
2. Summarize this email's contents using [OpenAI's API](https://platform.openai.com/overview), with a default prompt
3. Send the summary back to ravigahlla@gmail.com, along with:
   4. the default prompt used to summarize
   5. whether you want to re-summarize the email according to an updated, custom prompt, in the form of an email reply 
   6. and response whether you want this updated prompt to be the new standard default
   7. repeat the summary process

NOTE: you'll need an account balance with OpenAI, a gmail account 
[with your app pass key setup](https://support.google.com/mail/answer/185833?hl=en), setup with auto-renewal, in order to make this work
Setups
1. download the repo, and go to the project directory
2. you need to create your own .config file, containing your credentials (e.g., gmail app pass, openai key, etc)
3. run 'sudo chmod 600 .config' to give yourself permission to read from the file
4. run 'install .' to run setup.py, and install the right dependencies
5. run 'python3 src/main.py'


Requirements:
- you'll want to create a .config file to store your credentials, and place in the main directory (in stratecheryGPT)
- an account with OpenAI, so you can connect to their API, using the credentials in your .config
- I'm using my gmail, so you'll need to get an app passkey to place within your .config file
- Set urllib3 < 1.0 with this command


***TODO***
- ~~need to handling token limits (4096)~~
- create a test flag, which will reference variables with various test values (and then a "PROD" state, which will
make it ready for public-use)
- better handle error handling in the try catch code properly (openai.error doesn't exist, so need to find updated version)
- setup this script on a separate server (or a Raspberry Pi)
- set a cron job to either run at a specific time, or ping my email and send me a summary
- make this server interactive: I can email back a reply, and then get a response, if I want to dig deeper
- setup another email handle (e.g., 'summarizerbot@?')
- be LLM agnostic (support for OpenAI, Gemini, or a combination of all)
- deal with rich-content email (embedded video, audio) summarization
 