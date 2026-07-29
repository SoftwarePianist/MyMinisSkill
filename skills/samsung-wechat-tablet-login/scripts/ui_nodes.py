#!/usr/bin/env python3
import argparse, json, sys

def load(path):
    with open(path, 'r', encoding='utf-8') as f:
        raw = f.read().strip()
    obj = json.loads(raw)
    data = obj.get('data', obj)
    nodes = data.get('nodes') or data.get('data') or []
    return nodes

def val(n, key, default=''):
    v = n.get(key, default)
    return default if v is None else v

def center(n):
    c = n.get('center') or {}
    return int(c.get('x', -1)), int(c.get('y', -1))

def matches(n, q, field, exact):
    fields = []
    if field in ('any','text'): fields.append(str(val(n,'text')))
    if field in ('any','desc'): fields.append(str(val(n,'contentDesc')))
    ql = q.casefold()
    return any((s.casefold() == ql if exact else ql in s.casefold()) for s in fields if s)

def compact(n):
    x,y=center(n)
    return {'nodeId':val(n,'nodeId'),'text':val(n,'text'),'contentDesc':val(n,'contentDesc'),
            'clickable':bool(val(n,'clickable',False)),'enabled':bool(val(n,'enabled',True)),
            'scrollable':bool(val(n,'scrollable',False)),'x':x,'y':y,
            'bounds':n.get('bounds') or {},'depth':val(n,'depth',-1)}

def find(nodes,q,field='any',exact=False):
    hits=[(i,n) for i,n in enumerate(nodes) if matches(n,q,field,exact)]
    if not hits and exact: hits=[(i,n) for i,n in enumerate(nodes) if matches(n,q,field,False)]
    return hits

def tap_plan(nodes,q,field='any',exact=False):
    hits=find(nodes,q,field,exact)
    if not hits: return None
    # Prefer an enabled, clickable exact match.
    for i,n in hits:
        if n.get('clickable') and n.get('enabled',True):
            return {'strategy':'target_node','target':compact(n),'tap':compact(n)}
    i,n=hits[0]; tx,ty=center(n); tb=n.get('bounds') or {}
    # A clickable wrapper that geometrically contains the label is best.
    containing=[]
    for j,c in enumerate(nodes):
        b=c.get('bounds') or {}
        if not (c.get('clickable') and c.get('enabled',True) and b): continue
        if b.get('left',1)<=tx<=b.get('right',-1) and b.get('top',1)<=ty<=b.get('bottom',-1):
            area=max(1,(b['right']-b['left'])*(b['bottom']-b['top']))
            containing.append((area,abs(j-i),c))
    if containing:
        c=sorted(containing,key=lambda z:(z[0],z[1]))[0][2]
        return {'strategy':'containing_node','target':compact(n),'tap':compact(c)}
    # Samsung Settings commonly emits a clickable row immediately before its label.
    for span in (1,2,3):
        j=i-span
        if j>=0:
            c=nodes[j]; cx,cy=center(c)
            if c.get('clickable') and c.get('enabled',True) and abs(cy-ty)<=180:
                return {'strategy':'previous_clickable','target':compact(n),'tap':compact(c)}
    # Direct label coordinates often work even when clickable=false.
    if tx>=0 and ty>=0:
        return {'strategy':'target_xy','target':compact(n),'tap':compact(n)}
    for span in (1,2,3):
        j=i+span
        if j<len(nodes):
            c=nodes[j]; cx,cy=center(c)
            if c.get('clickable') and c.get('enabled',True) and abs(cy-ty)<=180:
                return {'strategy':'following_clickable','target':compact(n),'tap':compact(c)}
    return None

def viewport(nodes):
    right=bottom=0
    for n in nodes:
        b=n.get('bounds') or {}
        right=max(right,int(b.get('right',0))); bottom=max(bottom,int(b.get('bottom',0)))
    if not right or not bottom:
        xs=[]; ys=[]
        for n in nodes:
            x,y=center(n)
            if x>=0: xs.append(x)
            if y>=0: ys.append(y)
        if xs: right=max(xs)+max(20,max(xs)//25)
        if ys: bottom=max(ys)+max(40,max(ys)//25)
    return {'width':right,'height':bottom}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('file'); p.add_argument('command',choices=['find','tap-plan','labels','viewport','signature','scrollable','zone'])
    p.add_argument('query',nargs='?',default=''); p.add_argument('--field',choices=['any','text','desc'],default='any')
    p.add_argument('--exact',action='store_true')
    a=p.parse_args(); nodes=load(a.file)
    if a.command=='find':
        hits=find(nodes,a.query,a.field,a.exact); print(json.dumps([compact(n) for _,n in hits],ensure_ascii=False))
    elif a.command=='tap-plan':
        plan=tap_plan(nodes,a.query,a.field,a.exact)
        if not plan: sys.exit(1)
        print(json.dumps(plan,ensure_ascii=False))
    elif a.command=='labels':
        for n in nodes:
            s=val(n,'text') or val(n,'contentDesc')
            if s: print(s)
    elif a.command=='viewport': print(json.dumps(viewport(nodes)))
    elif a.command=='scrollable':
        candidates=[]
        for n in nodes:
            if not n.get('scrollable'): continue
            b=n.get('bounds') or {}; area=max(1,(b.get('right',0)-b.get('left',0))*(b.get('bottom',0)-b.get('top',0)))
            candidates.append((area,n))
        if not candidates: sys.exit(1)
        print(json.dumps(compact(sorted(candidates,key=lambda z:z[0],reverse=True)[0][1]),ensure_ascii=False))
    elif a.command=='zone':
        hits=find(nodes,a.query,a.field,a.exact)
        if not hits: print('absent'); return
        vp=viewport(nodes); h=vp['height']; y=center(hits[0][1])[1]
        if h<=0 or y<0: print('absent')
        elif y<h*.15: print('above')
        elif y>h*.85: print('below')
        else: print('safe')
    else:
        labels=sorted(set((val(n,'text') or val(n,'contentDesc')).strip() for n in nodes if (val(n,'text') or val(n,'contentDesc')).strip()))
        print('|'.join(labels))
if __name__=='__main__': main()
