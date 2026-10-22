import numpy as np, wave
SR=44100; DUR=96.0; n=int(SR*DUR); t=np.arange(n)/SR
BPM=112; beat=60/BPM; bar=beat*4
out=np.zeros((n,2))
def lp(x,a):  # one-pole lowpass, vectorized via lfilter-like loop in chunks
    y=np.empty_like(x); s=0.0
    for i in range(len(x)): s+=a*(x[i]-s); y[i]=s
    return y
def saw(f,tt): return 2*((tt*f)%1)-1
mid=lambda m:440*2**((m-69)/12)
prog=[[57,60,64],[53,57,60],[48,52,55],[55,59,62]]   # Am F C G
roots=[45,41,36,43]
# pad
pad=np.zeros(n)
for i in range(int(DUR/(bar*2))+1):
    s=int(i*bar*2*SR); e=min(n,int((i+1)*bar*2*SR)+int(0.3*SR))
    if s>=n: break
    tt=t[s:e]-t[s]; env=np.minimum(1,tt/0.8)*np.minimum(1,np.maximum(0,(t[e-1]-t[s]-tt)/0.4))
    ch=prog[i%4]; sig=sum(saw(mid(m)*d,tt) for m in ch for d in (0.997,1.003))/12
    pad[s:e]+=sig*env
pad=lp(pad,0.06)
# bass + sidechain
bass=np.zeros(n); kick=np.zeros(n); hat=np.zeros(n)
nb=int(DUR/beat)
rng=np.random.default_rng(1)
for k in range(nb*2):
    s=int(k*beat/2*SR); L=int(beat/2*SR*0.9); 
    if s+L>=n: break
    tt=np.arange(L)/SR; r=roots[int(k*beat/2/(bar*2))%4]
    bass[s:s+L]+=np.sin(2*np.pi*mid(r)*tt)*np.exp(-tt*5)*0.9+saw(mid(r),tt)*0.15*np.exp(-tt*8)
for k in range(nb):
    s=int(k*beat*SR); tb=k*beat
    if 6<=tb<92 and not(83<tb<84.3):
        L=int(0.35*SR); tt=np.arange(L)/SR
        f=50+90*np.exp(-tt*30); ph=2*np.pi*np.cumsum(f)/SR
        kick[s:s+L]+=np.sin(ph)*np.exp(-tt*9)
    if 12<=tb<92:
        s2=s+int(beat/2*SR); L=int(0.06*SR)
        if s2+L<n: hat[s2:s2+L]+=rng.standard_normal(L)*np.exp(-np.arange(L)/SR*70)*0.25
hat=hat-lp(hat,0.5)
# sidechain envelope
sc=np.ones(n)
for k in range(nb):
    tb=k*beat
    if 6<=tb<92:
        s=int(tb*SR); L=int(beat*SR); tt=np.arange(min(L,n-s))/SR; sc[s:s+len(tt)]=1-0.55*np.exp(-tt*9)
mix=pad*0.55*sc+bass*0.35*sc*np.clip((t-5)/1,0,1)+kick*0.6+hat
# whoosh + impacts
for T in [12,46,84,6,15,23,31,37,49,58,64,72,78,92]:
    big=T in (12,46,84)
    L=int((1.6 if big else 0.7)*SR); s=int((T-(1.2 if big else 0.45))*SR)
    tt=np.arange(L)/SR; x=rng.standard_normal(L)
    env=np.sin(np.pi*np.clip(tt/(L/SR),0,1))**2
    a=np.linspace(0.02,0.35,L)
    y=np.empty(L); st=0
    for i in range(L): st+=a[i]*(x[i]-st); y[i]=st
    mix[s:s+L]+=y*env*(0.9 if big else 0.35)
    if big:
        s=int(T*SR); L=int(1.2*SR); tt=np.arange(L)/SR
        mix[s:s+L]+=np.sin(2*np.pi*(40+30*np.exp(-tt*6))*tt)*np.exp(-tt*3)*0.8
# fades
mix*=np.clip(t/1.5,0,1)*np.clip((DUR-t)/3,0,1)
mix/=np.max(np.abs(mix))*1.12
L=mix; R=np.roll(mix,int(0.012*SR))*0.9+mix*0.1
st=np.stack([L,R],1)
w=wave.open('out/music.wav','wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((st*32767).astype('<i2').tobytes()); w.close()
print('ok')
