const menu=document.querySelector('.menu');const mobile=document.querySelector('.mobile-nav');function closeMenu(){menu.classList.remove('open');mobile.classList.remove('open');menu.setAttribute('aria-expanded','false');mobile.setAttribute('aria-hidden','true');document.body.style.overflow=''}menu.addEventListener('click',()=>{const open=!mobile.classList.contains('open');menu.classList.toggle('open',open);mobile.classList.toggle('open',open);menu.setAttribute('aria-expanded',String(open));mobile.setAttribute('aria-hidden',String(!open));document.body.style.overflow=open?'hidden':''});mobile.querySelectorAll('a').forEach(a=>a.addEventListener('click',closeMenu));addEventListener('scroll',()=>document.querySelector('header').classList.toggle('scrolled',scrollY>40),{passive:true});
const form = document.querySelector('#form');
const day = form.elements.day;
const now = new Date();
day.min = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
day.addEventListener('change',()=>{const d=new Date(day.value+'T12:00:00');day.setCustomValidity(d.getDay()===0?'Please choose Monday to Saturday.':'');form.elements.time.max=d.getDay()===6?'15:45':'19:45';});
form.addEventListener('submit',async e=>{
 e.preventDefault();const button=form.querySelector('button');const message=form.querySelector('.success');
 button.disabled=true;message.textContent='Saving your request…';
 try {const response=await fetch('/api/requests',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(form)))});const result=await response.json();if(!response.ok)throw new Error(result.error||'Could not save request.');message.textContent=`Request ${result.id} saved. Your appointment is not yet confirmed. The team will contact you.`;form.reset();}
 catch(error){message.textContent=error.message==='Failed to fetch'?'Connection unavailable. Please try again.':(error instanceof SyntaxError?'Booking service is unavailable. Please try again later.':error.message);}
 finally{button.disabled=false;}
});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeMenu();});
