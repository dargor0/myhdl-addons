/*
 GHDL VHPI interface for MyHDL
 
 Custom interface format:
 
 client->server:
 [<command>] <time> <arg1> ... <arg-n>\n
 
 server->client
 [<response>] <time> <arg1> ... <arg-n>\n

 Example
wpipe>FROM 0 B 2
rpipe<OK
>TO 0 G 2 
<OK
>>>START 
<OK 
>>>0 
<0 
>>>0 
<0 0
>>>0 G 0 
<0
>>>0 
<10
>>>10 
<10
>>>10 <<< 
<10<<< 
>>>10 <<< 
<10 1<<< 
>>>10 G 1 <<< 
<10<<< 
>>>10 <<< 
<20<<< 
>>>20 <<< 
<20<<< 
>>>20 <<< 
<20 2<<< 
>>>20 G 3 <<< 
<20<<< 

    FROM => output to MyHDL module, input to VHDL stub
    TO => input to MyHDL module, output to VHDL stub
 
 */


#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <linux/un.h>

//#define USE_SOCKETS 1

#define FLAG_HAS_CHANGED 0x1
#define FLAG_INITIAL_VAL 0x2

#define MAX_STRING 256
#define d_perror perror
#define debug printf

// codes for update_signal return value
#define UPDATE_ERROR -1 
#define UPDATE_END    0 // end simulation
#define UPDATE_SIGNAL 1 // next update need a signal trigger or small time delay
#define UPDATE_TIME   2 // next update will be at a time delay
#define UPDATE_DELTA  3 // next update need a delta step

// static info
static int open_sockfd = -1;
static char socket_path[MAX_STRING];
static int init_pipes_flag = 0;
static int rpipe;
static int wpipe;

static char cosim_from_signals[MAX_STRING];
static char cosim_to_signals[MAX_STRING];
static int cosim_init_flag = 0;

static uint64_t vhdl_time_res = 0;
static uint64_t vhdl_curtime = 0;
static uint64_t myhdl_curtime = 0;
static uint64_t myhdl_next_trigger = 0;

// signal mapping
static int cosim_fs_count = 0;
static int cosim_ts_count = 0;
static int cosim_fs_bitsize = 0;
static int cosim_ts_bitsize = 0;
static int cosim_fs_bytesize = 0;
static int cosim_ts_bytesize = 0;
typedef struct sigentry {
    char name[MAX_STRING];
    int size;
    int flags;
    union {
        uint32_t value;
        uint32_t * ptrvalue;
    };
} sigentry_t;
static sigentry_t * cosim_from_set;
static sigentry_t * cosim_to_set;

// prototypes
static int init_pipes();
static int init_socket();
static void d_print_rawdata(uint32_t * data, int len, char * premsg);
static void d_print_sigset(sigentry_t * base, int len, char * premsg);
static int parse_init(char * input);
static int sendrecv(char * buf, int max_len);
void intseq_to_signals(uint32_t * datain);

int startup_simulation (uint64_t time, uint64_t time_res, char ** from_signals, char ** to_signals);
int update_signal (uint32_t ** datain, uint32_t ** dataout, uint64_t time);
uint64_t next_timetrigger(uint64_t curtime);

static int init_pipes()
{
    char *w;
    char *r;

    if (init_pipes_flag) {
        return 0;
    }

    if ((w = getenv("MYHDL_TO_PIPE")) == NULL) {
        d_perror("getenv");
        debug("VHPI: error on getenv MYHDL_TO_PIPE\n");
        return -1;
    }
    if ((r = getenv("MYHDL_FROM_PIPE")) == NULL) {
        d_perror("getenv");
        debug("VHPI: error on getenv MYHDL_FROM_PIPE\n");
        return -1;
    }
    wpipe = atoi(w);
    rpipe = atoi(r);
    debug("DEBUG: setup pipes done\n");
    init_pipes_flag = 1;
    return 0;
}

static int init_socket()
{
    char *s;
    int sockfd;
    struct sockaddr_un addr;

    if (open_sockfd > 0) {
        return open_sockfd;
    }

    if ((s = getenv("MYHDL_SOCKET")) == NULL) {
        d_perror("getenv");
        debug("VHPI: error on getenv\n");
        return -1;
    }
    strncpy(socket_path, s, MAX_STRING);
    
    sockfd = socket(PF_UNIX, SOCK_STREAM, 0);
    if(sockfd < 0) {
        d_perror("socket");
        debug("VHPI: error on socket\n");
        return sockfd;
    } 
    
    unlink(socket_path);
    
    addr.sun_family = AF_UNIX;
    snprintf(addr.sun_path, UNIX_PATH_MAX, socket_path);
    
    if (connect(sockfd, (struct sockaddr *) &addr, sizeof(addr)) == -1) {
        d_perror("connect");
        debug("VHPI: error on connect\n");
        close(sockfd);
        return -1;
    }
    
    open_sockfd = sockfd;
    
    debug("VHPI: unix socket in %s sockfd %d\n", socket_path, sockfd);
    
    return open_sockfd;
}

static void d_print_rawdata(uint32_t * data, int len, char * premsg)
{
    int i , nbytes;
    char buf[MAX_STRING];
    for(i = 0, nbytes = 0; i < len; i++) {
        nbytes += snprintf(&(buf[nbytes]), MAX_STRING - nbytes, " %d ", data[i]);
    }
    debug("VHPI: %s data output: %s\n", premsg, buf);
}

static void d_print_sigset(sigentry_t * base, int len, char * premsg)
{
    int i, j, nbytes, valbytes;
    char buf[MAX_STRING];
    for(i = 0, nbytes = 0; i < len; i++) {
        nbytes += snprintf(&(buf[nbytes]), MAX_STRING - nbytes, " %s_%d;0x%x", base[i].name, base[i].size, base[i].flags);
        if(base[i].size <= 32) {
            nbytes += snprintf(&(buf[nbytes]), MAX_STRING - nbytes, ",0x%x", base[i].value);
        } else {
            valbytes = (base[i].size / 32) + 1;
            for(j = 0; j < valbytes; j++) {
                nbytes += snprintf(&(buf[nbytes]), MAX_STRING - nbytes, ",0x%x", base[i].ptrvalue[j]);
            }
        }
    }
    debug("VHPI: %s sigentry output: %s\n", premsg, buf);
}

static int parse_init(char * input)
{
    char buf[MAX_STRING];
    char *bufptr, *token;
    int names_count, sizes_count;
    long tmpnumber;
    
    strncpy(buf, input, MAX_STRING);
    
    // input format: <name> <size> ... <name-n> <size-n>
    
    token = strtok_r(buf, " ", &bufptr);
    for(names_count = sizes_count = 0; token != NULL;) {
        // first element: name
        names_count++;
        // ---
        token = strtok_r(NULL, " ", &bufptr);
        if(token == NULL) break;
        // second element: bitsize
        // check if is a positive number (non-zero)
        if(sscanf(token, "%li", &tmpnumber) < 0) break;
        if(tmpnumber <= 0) break;
        sizes_count++;
        // ---
        token = strtok_r(NULL, " ", &bufptr);
    }
    if(names_count != sizes_count) return -1;
    else return names_count;
}

static int sendrecv(char * buf, int max_len)
{
    int retval, nbytes;
    
    nbytes = strlen(buf);
    
    debug("VHPI: wpipe sending  >>>%s<<<\n", buf);
#ifdef USE_SOCKETS
    retval = send(open_sockfd, buf, nbytes, MSG_NOSIGNAL);
#else
    retval = write(wpipe, buf, nbytes);
#endif
    if(retval <= 0) {
        // check for EPIPE error: simply return 0 bytes read
        if(errno == EPIPE) return 0;
        d_perror("send");
        debug("VHPI: error on send (%d)\n", retval);
        return retval;
    }
    
#ifdef USE_SOCKETS   
    nbytes = recv(open_sockfd, buf, max_len, MSG_NOSIGNAL);
#else
    nbytes = read(rpipe, buf, max_len);
#endif
    if(nbytes < 0) {
        d_perror("recv");
        debug("VHPI: error on recv (%d)\n", nbytes);
        return nbytes;
    }
    if(nbytes == 0) return nbytes;

    if(nbytes < max_len) {
        if(buf[nbytes] != '\0') {
            buf[nbytes] = '\0';
            nbytes++;
        }
        debug("VHPI: rpipe received >>>%s<<<\n", buf);
        return nbytes;
    } else {
        buf[max_len-1] = '\0';
        debug("VHPI: rpipe recv max >>>%s<<<\n", buf);
        return max_len;
    }
}

void intseq_to_signals(uint32_t * datain)
{
    int intidx, bitidx, setidx, size, dif, values_count, arrayidx;
    uint32_t tmpvalue;
    
    intidx = 0;
    bitidx = 0;
    setidx = 0;
    dif = 0;
    values_count = 0;
    tmpvalue = 0;
    
    for(;setidx < cosim_ts_count ;setidx++) {
        size = cosim_to_set[setidx].size;
        if(size <= 32) {
            if(bitidx + size > 32){
                dif = bitidx + size - 32;
                // first part
                tmpvalue = (datain[intidx] >> bitidx) & ((1 << (size - dif)) - 1);
                intidx++;
                if(intidx >= cosim_ts_bytesize) break;
                // second part
                tmpvalue |= (datain[intidx] & ((1 << dif) - 1)) << (size - dif);
                bitidx = dif;
            } else {
//                 tmpvalue = datain[intidx];
//                 tmpvalue >>= bitidx;
//                 tmpvalue &= (1 << size) - 1;
                tmpvalue = (datain[intidx] >> bitidx) & ((1 << size) - 1);
                bitidx += size;
            }
            if (cosim_to_set[setidx].value != tmpvalue){
                cosim_to_set[setidx].value = tmpvalue;
                cosim_to_set[setidx].flags |= FLAG_HAS_CHANGED;
            }
        } else {
            values_count = (cosim_to_set[setidx].size / 32) + 1;
            for(arrayidx = 0; arrayidx < values_count; arrayidx++) {
                if(arrayidx < (values_count - 1)) {
                    size = cosim_to_set[setidx].size % 32;
                } else {
                    size = 32;
                }
                if(bitidx + size > 32){
                    dif = bitidx + size - 32;
                    // first part
                    tmpvalue = (datain[intidx] >> bitidx) & ((1 << (size - dif)) - 1);
                    intidx++;
                    if(intidx >= cosim_ts_bytesize) break;
                    // second part
                    tmpvalue |= (datain[intidx] & ((1 << dif) - 1)) << (size - dif);
                    bitidx = dif;
                } else {
                    tmpvalue = (datain[intidx] >> bitidx) & ((1 << size) - 1);
                    bitidx += size;
                }
                if(cosim_to_set[setidx].ptrvalue[arrayidx] != tmpvalue) {
                    cosim_to_set[setidx].ptrvalue[arrayidx] = tmpvalue;
                    cosim_to_set[setidx].flags |= FLAG_HAS_CHANGED;
                }
            }
        }
        if (bitidx == 32) {
            intidx++;
            bitidx = 0;
        }
        if(intidx >= cosim_ts_bytesize) break;
    }
}

void signals_to_intseq(uint32_t * dataout)
{
    int intidx, bitidx, setidx, size, dif, values_count, arrayidx;
    uint32_t tmpvalue;
    
    intidx = 0;
    bitidx = 0;
    setidx = 0;
    dif = 0;
    values_count = 0;
    tmpvalue = 0;
    
    for(;setidx < cosim_fs_count ;setidx++) {
        size = cosim_from_set[setidx].size;
        if(size <= 32) {
            if(bitidx + size > 32){
                dif = bitidx + size - 32;
                // first part
                tmpvalue = cosim_from_set[setidx].value;
                tmpvalue &= (1 << (size - dif)) - 1;
                tmpvalue <<= bitidx;
                dataout[intidx] &= ~(((1 << (size - dif)) - 1) << bitidx);
                dataout[intidx] |= tmpvalue;
                intidx++;
                if(intidx >= cosim_fs_bytesize) break;
                // second part
                tmpvalue = cosim_from_set[setidx].value;
                tmpvalue >>= dif;
                tmpvalue &= (1 << dif) - 1;
                dataout[intidx] &= ~((1 << dif) - 1);
                dataout[intidx] = tmpvalue;
                bitidx = dif;
            } else {
                tmpvalue = cosim_from_set[setidx].value;
                tmpvalue &= (1 << size) - 1;
                tmpvalue <<= bitidx;
                // mask for added value
                dataout[intidx] &= ~(((1 << size) - 1) << bitidx);
                dataout[intidx] |= tmpvalue;
                bitidx += size;
            }
        } else {
            values_count = (cosim_from_set[setidx].size / 32) + 1;
            for(arrayidx = 0; arrayidx < values_count; arrayidx++) {
                if(arrayidx < (values_count - 1)) {
                    size = cosim_from_set[setidx].size % 32;
                } else {
                    size = 32;
                }
                if(bitidx + size > 32){
                    dif = bitidx + size - 32;
                    // first part
                    tmpvalue = cosim_from_set[setidx].ptrvalue[arrayidx];
                    tmpvalue &= (1 << (size - dif)) - 1;
                    tmpvalue <<= bitidx;
                    dataout[intidx] &= ~(((1 << (size - dif)) - 1) << bitidx);
                    dataout[intidx] |= tmpvalue;
                    intidx++;
                    if(intidx >= cosim_fs_bytesize) break;
                    // second part
                    tmpvalue = cosim_from_set[setidx].ptrvalue[arrayidx];
                    tmpvalue >>= dif;
                    tmpvalue &= (1 << dif) - 1;
                    dataout[intidx] &= ~((1 << dif) - 1);
                    dataout[intidx] = tmpvalue;
                    bitidx = dif;
                } else {
                    tmpvalue = cosim_from_set[setidx].value;
                    tmpvalue &= (1 << size) - 1;
                    tmpvalue <<= bitidx;
                    dataout[intidx] &= ~(((1 << size) - 1) << bitidx);
                    dataout[intidx] |= tmpvalue;
                    bitidx += size;
                }
            }
        }
        if (bitidx == 32) {
            intidx++;
            bitidx = 0;
        }
        if(intidx >= cosim_fs_bytesize) break;
    }
}

// external interface to cosim_core

/** startup_simulation
 * called on the start of simulation
 * 
 */
int startup_simulation (uint64_t time, uint64_t time_res, char ** from_signals, char ** to_signals)
{
    int retval, i, nbytes;
    char buf[MAX_STRING];
    char *bufptr, *token;
    
    debug("VHPI: startup_simulation:\n time = %ld\n time_res = %ld\n from_signals = (%p)>(%p) <%s>\n to_signals = (%p)>(%p) <%s>\n", time, time_res, from_signals, *from_signals, *from_signals, to_signals, *to_signals, *to_signals);
    
    // call once only
    if (cosim_init_flag) {
        debug("VHPI: startup_simulation called again.\n");
        return -1;
    }
    cosim_init_flag = 1;
    
    vhdl_time_res = time_res;
    vhdl_curtime = time;
    myhdl_curtime = time / vhdl_time_res;
    myhdl_next_trigger = 0;
    
    // gdb stuff
    debug("VHPI: PID = %d . Waiting 10 seconds to gdb attach.\n", getpid());
    //sleep(10);
    debug("VHPI: ... Done. You should be gdb attached now.\n");
    
#ifdef USE_SOCKETS
    retval = init_socket();
#else
    retval = init_pipes();
#endif
    if(retval < 0) return retval;
    
    strncpy(cosim_from_signals, *from_signals, MAX_STRING);
    strncpy(cosim_to_signals, *to_signals, MAX_STRING);
    
    // parse info
    cosim_fs_count = parse_init(cosim_from_signals);
    if(cosim_fs_count < 0) {
        debug("VHPI: parse error in from_signals (%s)\n", cosim_from_signals);
        return -1;
    }
    cosim_ts_count = parse_init(cosim_to_signals);
    if(cosim_ts_count < 0) {
        debug("VHPI: parse error in to_signals (%s)\n", cosim_to_signals);
        return -1;
    }
    
    cosim_from_set = (sigentry_t *) malloc(cosim_fs_count*sizeof(sigentry_t));
    cosim_to_set = (sigentry_t *) malloc(cosim_ts_count*sizeof(sigentry_t));
    if((cosim_from_set == NULL) || (cosim_to_set == NULL)) {
        d_perror("malloc");
        debug("VHPI: malloc error\n");
        return -1;
    }
    
    // extract FROM data
    strncpy(buf, cosim_from_signals, MAX_STRING);
    token = strtok_r(buf, " ", &bufptr);
    for(i = 0; i < cosim_fs_count; i++) {
        // first element: name
        strncpy(cosim_from_set[i].name, token, MAX_STRING);
        token = strtok_r(NULL, " ", &bufptr);
        // second element: bitsize
        sscanf(token, "%i", &(cosim_from_set[i].size));
        token = strtok_r(NULL, " ", &bufptr);
        // additional: value initialization
        cosim_from_set[i].flags = 0;
        if(cosim_from_set[i].size <= 32) cosim_from_set[i].value = 0;
        else {
            cosim_from_set[i].ptrvalue = (uint32_t *) malloc(((cosim_from_set[i].size/32)+1)*sizeof(uint32_t));
            if(cosim_from_set[i].ptrvalue == NULL) {
                d_perror("malloc");
                debug("VHPI: malloc error\n");
                return -1;
            }
        }
        // bitsize increment
        cosim_fs_bitsize += cosim_from_set[i].size;
    }
    cosim_fs_bytesize = (cosim_fs_bitsize / 32) + 1;

    // extract TO data
    strncpy(buf, cosim_to_signals, MAX_STRING);
    token = strtok_r(buf, " ", &bufptr);
    for(i = 0; i < cosim_ts_count; i++) {
        // first element: name
        strncpy(cosim_to_set[i].name, token, MAX_STRING);
        token = strtok_r(NULL, " ", &bufptr);
        // second element: bitsize
        sscanf(token, "%i", &(cosim_to_set[i].size));
        token = strtok_r(NULL, " ", &bufptr);
        // additional: value initialization
        cosim_to_set[i].flags = FLAG_INITIAL_VAL;
        if(cosim_to_set[i].size <= 32) cosim_to_set[i].value = 0;
        else {
            cosim_to_set[i].ptrvalue = (uint32_t *) malloc(((cosim_to_set[i].size/32)+1)*sizeof(uint32_t));
            if(cosim_to_set[i].ptrvalue == NULL) {
                d_perror("malloc");
                debug("VHPI: malloc error\n");
                return -1;
            }
        }
        // bitsize increment
        cosim_ts_bitsize += cosim_to_set[i].size;
    }
    cosim_ts_bytesize = (cosim_ts_bitsize / 32) + 1;
    
    debug("VHPI: FROM %d signals => %d bits in %d bytes\n", cosim_fs_count, cosim_fs_bitsize, cosim_fs_bytesize);
    debug("VHPI: TO %d signals => %d bits in %d bytes\n", cosim_ts_count, cosim_ts_bitsize, cosim_ts_bytesize);
    
    snprintf(buf, MAX_STRING, "FROM %ld %s ", time, cosim_from_signals);
    
    nbytes = sendrecv(buf, MAX_STRING);
    if(nbytes <= 0) return retval;
    
    // check for OK
    if((buf[0] != 'O') && (buf[0] != 'K')) {
        debug("VHPI: error, MyHDL returned (%s)\n", buf);
        return -1;
    }
    
    snprintf(buf, MAX_STRING, "TO %ld %s ", time, cosim_to_signals);
    
    nbytes = sendrecv(buf, MAX_STRING);
    if(nbytes <= 0) return retval;
    
    if((buf[0] != 'O') && (buf[0] != 'K')) {
        debug("VHPI: error, MyHDL returned (%s)\n", buf);
        return -1;
    }
    
    // send start
    snprintf(buf, MAX_STRING, "START ");
    
    nbytes = sendrecv(buf, MAX_STRING);
    if(nbytes <= 0) return retval;
    
    if((buf[0] != 'O') && (buf[0] != 'K')) {
        debug("VHPI: error, MyHDL returned (%s)\n", buf);
        return -1;
    }
    
    debug("VHPI: startup_simulation: return 0\n");
    
    return 0;
}

/** update_signal
 * called on a change event on datain signals
 * 
 */
int update_signal (uint32_t ** datain, uint32_t ** dataout, uint64_t time)
{
    int retval, nbytes, i, j, valbytes, valindex;
    char buf[MAX_STRING];
    char val[MAX_STRING];
    char * bufptr, *valptr, *token;
    
    uint32_t *datain_ptr, *dataout_ptr;
    uint64_t myhdl_temptime, delta;
    
    debug("VHPI: update_signal:\n datain = %p\n dataout = %p\n time = %ld\n\n", datain, dataout, time);
    
#ifdef USE_SOCKETS
    retval = init_socket();
#else
    retval = init_pipes();
#endif
    if(retval < 0) return UPDATE_ERROR;
    
    datain_ptr = *datain;
    dataout_ptr = *dataout;
    
    d_print_rawdata(datain_ptr, cosim_ts_bytesize, "datain");
    
    // convert datain to signal values (to put in TO signal set)
    intseq_to_signals(datain_ptr);
    
    d_print_sigset(cosim_to_set, cosim_ts_count, "TO_set");
    
    // prepare time counter
    vhdl_curtime = time;
    myhdl_temptime = time / vhdl_time_res;
    delta = time % vhdl_time_res;
    nbytes = snprintf(buf, MAX_STRING, "%ld ", myhdl_temptime);
    debug("VHPI: prev_myhdl_time = %ld , myhdl_time = %ld , delta = %ld\n", myhdl_curtime, myhdl_temptime, delta);
    myhdl_curtime = myhdl_temptime;
    bufptr = &(buf[nbytes]);
    
    for(i = 0; i < cosim_ts_count; i++) {
        if(cosim_to_set[i].flags & FLAG_HAS_CHANGED) {
            // convert value to string
            if(cosim_to_set[i].size > 32) {
                valbytes = 0;
                for(j = (cosim_to_set[i].size / 32); j >= 0 ; j--) {
                    valptr = &(val[valbytes]);
                    valbytes = snprintf(valptr, MAX_STRING - valbytes, "%x_", cosim_to_set[i].ptrvalue[j]);
                }
            } else {
                snprintf(val, MAX_STRING, "%x", cosim_to_set[i].value);
            }
            nbytes += snprintf(bufptr, MAX_STRING - nbytes, "%s %s ", cosim_to_set[i].name, val);
            bufptr = &(buf[nbytes]);
            cosim_to_set[i].flags &= ~FLAG_HAS_CHANGED;
        }
    }
    
    nbytes = sendrecv(buf, MAX_STRING);
    if(nbytes < 0) return UPDATE_ERROR;
    if(nbytes == 0) {
        debug("VHPI: MyHDL pipe closed.\n");
        return UPDATE_END;
    }
    
    // check results back, probably put in FROM signal set
    // format: <time> [<data-1> ... <data-n>]
    
    token = strtok_r(buf, " ", &bufptr);
    sscanf(token, "%li", &myhdl_temptime);
    debug("VHPI: cur_myhdl_time = %ld , next_myhdl_time = %ld\n", myhdl_curtime, myhdl_temptime);
    
    for(i = 0; i < cosim_fs_count; i++) {
        token = strtok_r(NULL, " ", &bufptr);
        if(token == NULL) break;
        // save data
        if(cosim_from_set[i].size > 32) {
            // read 8 bytes at a time (enough to hold 32 bits in hexadecimal format)
            val[8] = '\0';
            valindex = 0;
            for(j = strlen(token) - 8; j > 0 ; j -= 8) {
                strncpy(val, token, 8);
                sscanf(val, "%i", &(cosim_from_set[i].ptrvalue[valindex]));
                valindex++;
            }
            strncpy(val, token, j);
            val[j] = '\0';
            sscanf(val, "%i", &(cosim_from_set[i].ptrvalue[valindex]));
        } else {
            sscanf(token, "%i", &(cosim_from_set[i].value));
        }
    }
    
    d_print_sigset(cosim_from_set, cosim_fs_count, "FROM_set");
    
    // put in dataout
    if(i == 0) {
        debug("VHPI: no update from myhdl.\n");
        retval = UPDATE_DELTA;
    } else {
        debug("VHPI: update %d signals from myhdl.\n", cosim_fs_count);
        signals_to_intseq(dataout_ptr);
        retval = UPDATE_SIGNAL;
    }
    
    d_print_rawdata(dataout_ptr, cosim_fs_bytesize, "dataout");
    
    // time check
    if(myhdl_temptime > myhdl_curtime) {
        debug("VHPI: myhdl call for time step to %li.\n", myhdl_temptime);
        myhdl_next_trigger = myhdl_temptime;
        retval = UPDATE_TIME;
    }
    
    // hack: update outputs on time 0 on the right moment
    if((retval == UPDATE_DELTA) && (vhdl_curtime == 0)) {
        for(i = 0; i < cosim_ts_count; i++) {
            if(cosim_to_set[i].flags & FLAG_INITIAL_VAL) {
                debug("VHPI: hack for time 0 signal %s (prev flags %d).\n", cosim_to_set[i].name, cosim_to_set[i].flags);
                cosim_to_set[i].flags |= FLAG_HAS_CHANGED;
                cosim_to_set[i].flags &= ~FLAG_INITIAL_VAL;
                debug("VHPI: hack for time 0 signal %s (flags %d).\n", cosim_to_set[i].name, cosim_to_set[i].flags);
            }
        }
    }
    
    debug("VHPI: update_signal: return %d\n", retval);
    
    return retval;
}
  
uint64_t next_timetrigger(uint64_t curtime)
{
    uint64_t myhdl_temptime, delta;
    
    myhdl_temptime = curtime / vhdl_time_res;
    delta = curtime % vhdl_time_res;
    
    debug("VHPI: next_timetrigger: temp_time %li delta %li\n", myhdl_temptime, delta);
    
    if(myhdl_next_trigger > myhdl_temptime) {
        delta = (myhdl_next_trigger - myhdl_temptime) * vhdl_time_res;
        debug("VHPI: next_timetrigger: next VHDL trigger in %li\n", delta);
        return delta;
    } else {
        return vhdl_time_res;
    }
}
