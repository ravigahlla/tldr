# stratecheryGPT
A summarizer to deal with Stratechery's incessant daily emails

**Problem**: [Stratechery](https://stratechery.com/) is a daily newsletter for technology that can contain
valuable content, but it is too verbose, and the inability to digest these daily newsletters adds up, causing valuable
information to be missed (investment opportunities, strategic shifts)

**Solution**: Use OpenAI's GPT API in order to summarize the daily email newsletters according to a prompt designed to 
extract the most useful information

*Program Design*
1. Have a cron job which runs daily, looking for emails from email@stratechery.com
2. Using a default prompt, summarize this email's contents using [OpenAI's API](https://platform.openai.com/overview)
3. Send the summary back to ravigahlla@gmail.com, along with:
   4. the default prompt used to summarize
   5. whether you want to re-summarize the email according to an updated, custom prompt, in the form of an email reply and response
   6. whether you want this updated prompt to be the new standard default
   7. repeat the summary process


***FEATURES***
- ~~need to handling token limits (4096)~~
- will want to handle error handling in the try catch code properly (openai.error doesn't exist, so need to find updated version)
- creating a cron job
- dealing with rich-content email (embedded video, audio)
- be LLM agnostic (support for OpenAI, Gemini, or a combination of all)
- create a test flag, which will reference variables with various test values (and then a "PROD" state, which will
make it ready for public-use) 