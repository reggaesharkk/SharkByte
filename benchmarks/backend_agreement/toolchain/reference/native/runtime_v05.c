/* Freestanding, bounded Linux/AArch64 SharkByte bytecode interpreter. */
#include <stdint.h>
#include <stddef.h>

extern const unsigned char sb_program[];
extern const unsigned long sb_program_len;

#define FMAX 128
#define LMAX 1024
#define SMAX 65536
#define AMAX 4096
#define EMAX 65536
#define STEP_MAX 50000000ULL
#define HSIZE 11
#define V2P 6
#define V2D 10
#define BMAX (16U*1024U*1024U)

typedef struct { int64_t n; uint32_t h; uint8_t tag; } Value;
typedef struct { uint32_t fid, pc, end, base, retpc; Value locals[LMAX]; } Frame;
typedef struct { uint32_t start, end, arity, locals, name_start, name_len; } Function;
static Frame frames[FMAX];
static Function funcs[65535];
static Value stack[SMAX];
/* Version 1 encodes one program-wide slot count, not per-frame locals. */
static Value legacy_vars[65535];
static uint8_t boundaries[BMAX/8];
static int64_t heap[EMAX];
static uint32_t heap_start[AMAX], heap_len[AMAX];
static uint8_t heap_used[AMAX];
static uint32_t nf, depth=0, sp=0, n_arrays=0, n_elements=0;
static uint32_t legacy_slots=0;
static uint64_t steps=0;
static uint32_t v2=0;

static long sys_write(long fd, const void *buf, long n) {
    register long x0 __asm__("x0")=fd; register const void *x1 __asm__("x1")=buf;
    register long x2 __asm__("x2")=n; register long x8 __asm__("x8")=64;
    __asm__ volatile("svc 0":"+r"(x0):"r"(x1),"r"(x2),"r"(x8):"memory"); return x0;
}
static void sys_exit(long code) {
    register long x0 __asm__("x0")=code; register long x8 __asm__("x8")=93;
    __asm__ volatile("svc 0"::"r"(x0),"r"(x8):"memory"); for(;;){}
}
static void err(const char *s) { long n=0; while(s[n]) n++; sys_write(2,s,n); sys_write(2,"\n",1); sys_exit(70); }
static uint16_t u16(uint32_t p){ if(p+2>sb_program_len)err("Truncated operand"); return (uint16_t)sb_program[p]|((uint16_t)sb_program[p+1]<<8); }
static uint32_t u32(uint32_t p){ if(p+4>sb_program_len)err("Truncated operand"); return (uint32_t)sb_program[p]|((uint32_t)sb_program[p+1]<<8)|((uint32_t)sb_program[p+2]<<16)|((uint32_t)sb_program[p+3]<<24); }
static uint64_t u64(uint32_t p){ if(p+8>sb_program_len)err("Truncated operand"); uint64_t x=0; for(int i=7;i>=0;i--)x=(x<<8)|sb_program[p+i]; return x; }
static uint16_t read16(Frame *f){ if((uint64_t)f->pc+2>f->end)err("Truncated operand"); uint16_t v=(uint16_t)sb_program[f->pc]|((uint16_t)sb_program[f->pc+1]<<8); f->pc+=2; return v; }
static uint32_t read32(Frame *f){ if((uint64_t)f->pc+4>f->end)err("Truncated operand"); uint32_t v=(uint32_t)sb_program[f->pc]|((uint32_t)sb_program[f->pc+1]<<8)|((uint32_t)sb_program[f->pc+2]<<16)|((uint32_t)sb_program[f->pc+3]<<24); f->pc+=4; return v; }
static uint64_t read64(Frame *f){ if((uint64_t)f->pc+8>f->end)err("Truncated operand"); uint64_t v=0; for(int i=7;i>=0;i--)v=(v<<8)|sb_program[f->pc+i]; f->pc+=8; return v; }
static int known_opcode(uint8_t op){ return op==1||op==2||op==3||op==16||op==17||op==18||op==19||op==32||(op>=33&&op<=38)||(op>=40&&op<=52)||op==255; }
static uint32_t operand_len(uint8_t op){ if(op==1)return 8; if(op==2||op==3)return 2; if(op==40||op==41||op==42)return 4; if(op==46)return 4; return 0; }
static void mark_boundary(uint32_t p){ if(p>=BMAX)err("Bytecode exceeds native validation limit"); boundaries[p>>3]|=(uint8_t)(1U<<(p&7)); }
static int is_boundary(uint32_t p){ return p<BMAX && (boundaries[p>>3]&(uint8_t)(1U<<(p&7))); }
static int utf8_valid(uint32_t p,uint32_t n){
    uint32_t i=0;
    while(i<n){ uint8_t a=sb_program[p+i];
        if(a<0x80){i++;continue;}
        if(a>=0xc2&&a<=0xdf){if(i+1>=n||(sb_program[p+i+1]&0xc0)!=0x80)return 0;i+=2;continue;}
        if(a>=0xe0&&a<=0xef){if(i+2>=n)return 0;uint8_t b=sb_program[p+i+1],c=sb_program[p+i+2];if((c&0xc0)!=0x80||(b&0xc0)!=0x80||(a==0xe0&&b<0xa0)||(a==0xed&&b>=0xa0))return 0;i+=3;continue;}
        if(a>=0xf0&&a<=0xf4){if(i+3>=n)return 0;uint8_t b=sb_program[p+i+1],c=sb_program[p+i+2],d=sb_program[p+i+3];if((b&0xc0)!=0x80||(c&0xc0)!=0x80||(d&0xc0)!=0x80||(a==0xf0&&b<0x90)||(a==0xf4&&b>=0x90))return 0;i+=4;continue;}
        return 0;
    }
    return 1;
}
static void validate_code(uint32_t fid){
    Function *fn=&funcs[fid]; uint32_t pc=fn->start;
    while(pc<fn->end){
        mark_boundary(pc); uint8_t op=sb_program[pc++]; uint32_t n=operand_len(op);
        if(!known_opcode(op))err("Unknown opcode");
        if((uint64_t)pc+n>fn->end)err("Truncated operand");
        if(!v2&&(op>=46&&op<=52))err("Invalid opcode for bytecode version");
        if(v2&&op==255&&fid!=0)err("HALT outside main");
        if(v2&&op==47&&fid==0)err("RET from main");
        if(v2&&op==51&&fid==0)err("MISSING_RET in main");
        pc+=n;
    }
    if(pc!=fn->end)err("Malformed function body");
    pc=fn->start;
    while(pc<fn->end){
        uint8_t op=sb_program[pc++];
        if(op==40||op==41||op==42){ int32_t off=(int32_t)u32(pc); pc+=4; int64_t target=(int64_t)pc+off; if(target<fn->start||target>=fn->end||!is_boundary((uint32_t)target))err("Branch target is not an instruction boundary"); }
        else if(op==46){ uint16_t target=u16(pc),argc=u16(pc+2); pc+=4; if(!target||target>=nf)err("Invalid function target"); if(argc!=funcs[target].arity)err("Function arity mismatch"); }
        else pc+=operand_len(op);
    }
}
static void push(Value v){ if(sp>=SMAX)err("Operand stack limit exceeded"); stack[sp++]=v; }
static Value pop(void){ if(!sp)err("Stack underflow"); return stack[--sp]; }
static int64_t integer(Value v){ if(v.tag)err("Expected integer value"); return v.n; }
static Value iv(int64_t x){ Value v={x,0,0}; return v; }
static void parse_program(void){
    if(sb_program_len<HSIZE || sb_program[0]!='S'||sb_program[1]!='B'||sb_program[2]!='V'||sb_program[3]!='M')err("Invalid SharkByte format");
    if(sb_program_len>BMAX)err("Bytecode exceeds native validation limit");
    uint8_t ver=sb_program[4]; uint16_t count=u16(5); uint32_t payload=u32(7);
    if(HSIZE+payload!=sb_program_len)err("Invalid binary length");
    if(ver==1){ v2=0; nf=1; legacy_slots=count; funcs[0]=(Function){HSIZE,(uint32_t)sb_program_len,0,count,0,0}; validate_code(0); depth=1; frames[0].fid=0; frames[0].pc=HSIZE; frames[0].end=(uint32_t)sb_program_len; frames[0].base=0; frames[0].retpc=0; return; }
    if(ver!=2 || payload<V2P || sb_program[HSIZE]!='F'||sb_program[HSIZE+1]!='N'||sb_program[HSIZE+2]!='0'||sb_program[HSIZE+3]!='5')err("Invalid SharkByte format");
    v2=1; nf=u16(HSIZE+4); if(nf!=count||!nf)err("Invalid v2 function table");
    uint32_t p=HSIZE+V2P;
    for(uint32_t i=0;i<nf;i++){
        if(p+V2D>sb_program_len)err("Truncated function descriptor");
        uint16_t ar=u16(p), local=u16(p+2), nl=u16(p+4); uint32_t cl=u32(p+6); p+=V2D;
        uint64_t body=(uint64_t)p+nl, end=body+cl;
        if(local>LMAX||ar>local)err("Invalid function limits");
        if(!nl||end>sb_program_len)err("Invalid function descriptor");
        if(!utf8_valid(p,nl))err("Invalid function name encoding");
        funcs[i]=(Function){(uint32_t)body,(uint32_t)end,ar,local,p,nl}; p=(uint32_t)end;
    }
    if(p!=sb_program_len||depth)err("Invalid v2 function table");
    if(funcs[0].arity||funcs[0].name_len!=4||sb_program[funcs[0].name_start]!='m'||sb_program[funcs[0].name_start+1]!='a'||sb_program[funcs[0].name_start+2]!='i'||sb_program[funcs[0].name_start+3]!='n')err("Invalid main function");
    for(uint32_t i=0;i<nf;i++)for(uint32_t j=0;j<i;j++)if(funcs[i].name_len==funcs[j].name_len){ uint32_t k=0; while(k<funcs[i].name_len&&sb_program[funcs[i].name_start+k]==sb_program[funcs[j].name_start+k])k++; if(k==funcs[i].name_len)err("Invalid or duplicate function name"); }
    for(uint32_t i=0;i<nf;i++)validate_code(i);
    depth=1; frames[0].fid=0; frames[0].pc=funcs[0].start; frames[0].end=funcs[0].end; frames[0].base=0; frames[0].retpc=0;
}
static void print_int(int64_t x){ char b[32]; int n=0; uint64_t u; if(x<0){sys_write(1,"-",1); u=(uint64_t)(-(x+1))+1;}else u=(uint64_t)x; do{b[n++]=(char)('0'+u%10);u/=10;}while(u); while(n--)sys_write(1,&b[n],1); sys_write(1,"\n",1); }
static void run(void){
    parse_program();
    while(depth){
        if(++steps>STEP_MAX)err("Execution step limit exceeded");
        Frame *f=&frames[depth-1]; if(f->pc>=f->end)err("Missing HALT"); uint8_t op=sb_program[f->pc++];
        if(op==1){ push(iv((int64_t)read64(f))); }
        else if(op==2||op==3){ uint16_t i=read16(f); uint32_t lim=v2?funcs[f->fid].locals:legacy_slots; if(i>=lim)err("Invalid local index"); if(op==2)push(v2?f->locals[i]:legacy_vars[i]); else { Value value=pop(); if(v2)f->locals[i]=value; else legacy_vars[i]=value; } }
        else if(op==16||op==17||op==18||op==43||op==44){ int64_t b=integer(pop()),a=integer(pop()),r=0; if(op==16)r=(int64_t)((uint64_t)a+(uint64_t)b); else if(op==17)r=(int64_t)((uint64_t)a-(uint64_t)b); else if(op==18)r=(int64_t)((uint64_t)a*(uint64_t)b); else { if(!b)err("Division by zero"); if(a==INT64_MIN&&b==-1)err("Integer division overflow"); int64_t q=a/b,rem=a%b; r=op==43?q:rem; } push(iv(r)); }
        else if(op==19)push(iv((int64_t)(0-(uint64_t)integer(pop()))));
        else if(op>=33&&op<=38){ int64_t b=integer(pop()),a=integer(pop()); int r=op==33?a==b:op==34?a!=b:op==35?a<b:op==36?a<=b:op==37?a>b:a>=b; push(iv(r)); }
        else if(op==40||op==41||op==42){ int32_t off=(int32_t)read32(f); int take=op==42||(op==40?integer(pop())==0:integer(pop())!=0); if(take){int64_t dest=(int64_t)f->pc+off; if(dest<(v2?funcs[f->fid].start:HSIZE)||dest>=(v2?funcs[f->fid].end:(uint32_t)sb_program_len)||!is_boundary((uint32_t)dest))err("Branch target is not an instruction boundary");f->pc=(uint32_t)dest;} }
        else if(op==32)print_int(integer(pop()));
        else if(op==45){ int64_t c=integer(pop()); if(c<0||c>127)err("Character code outside ASCII range 0..127"); char ch=(char)c; sys_write(1,&ch,1); }
        else if(op==46){ if(!v2)err("Unknown opcode: 46"); uint16_t target=read16(f),argc=read16(f); if(!target||target>=nf)err("Invalid function target"); Function *fn=&funcs[target]; if(argc!=fn->arity)err("Function arity mismatch"); if(depth>=FMAX)err("Call depth limit exceeded"); if(sp<argc)err("Stack underflow"); Frame *callee=&frames[depth]; callee->fid=target; callee->pc=fn->start; callee->end=fn->end; callee->base=sp-argc; callee->retpc=f->pc; for(uint32_t i=0;i<fn->locals;i++)callee->locals[i]=iv(0); for(uint32_t i=0;i<argc;i++)callee->locals[i]=stack[sp-argc+i]; sp-=argc; depth++; }
        else if(op==47){ if(!v2||f->fid==0)err("RET from main"); if(sp!=f->base+1)err("Invalid return stack balance"); Value result=pop(); uint32_t ret=f->retpc; depth--; frames[depth-1].pc=ret; push(result); }
        else if(op==48){ if(!v2)err("Unknown opcode: 48"); int64_t n=integer(pop()); if(n<0)err("Negative array length"); if(n>65536||n_arrays>=AMAX||n_elements+(uint32_t)n>EMAX)err("Array heap limit exceeded"); uint32_t h=0; while(h<AMAX&&heap_used[h])h++; if(h==AMAX)err("Array heap limit exceeded"); heap_used[h]=1; heap_start[h]=n_elements; heap_len[h]=(uint32_t)n; for(uint32_t i=0;i<(uint32_t)n;i++)heap[n_elements+i]=0; n_elements+=(uint32_t)n;n_arrays++;Value a={0,h,1};push(a); }
        else if(op==49||op==50){ if(!v2)err("Unknown opcode: 49"); Value value=iv(0); if(op==50)value=pop(); int64_t idx=integer(pop()); Value arr=pop(); if(!arr.tag||arr.h>=AMAX||!heap_used[arr.h])err("Expected array reference"); if(idx<0||(uint64_t)idx>=heap_len[arr.h])err("Array index out of bounds"); uint32_t at=heap_start[arr.h]+(uint32_t)idx; if(op==49)push(iv(heap[at]));else heap[at]=integer(value); }
        else if(op==51)err("Function ended without return");
        else if(op==52){ if(!v2)err("Unknown opcode: 52"); (void)pop(); }
        else if(op==255){ if(f->fid!=0||depth!=1||sp||f->pc!=f->end)err("Invalid final VM state"); sys_exit(0); }
        else err("Unknown opcode");
    }
    err("Missing HALT");
}
int _start(void){ run(); return 0; }
