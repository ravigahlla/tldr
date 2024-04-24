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
   5. whether you want to re-summarize the email according to an updated, custom prompt
   6. whether you want this updated prompt to be the new standard default
   7. repeat the summary process


***NOTES***
- challenge with handling token limits (4096)
- challenge with calculating whether there are enough limits left in the ChatGPT account
- challenge with creating a cron job