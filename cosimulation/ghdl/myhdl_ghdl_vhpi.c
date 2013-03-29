/*
 GHDL VHPI interface for MyHDL
 
 Author:  Oscar Diaz <oscar.dc0@gmail.com>
 Date:    16-02-2013

 This code is free software; you can redistribute it and/or
 modify it under the terms of the GNU Lesser General Public
 License as published by the Free Software Foundation; either
 version 3 of the License, or (at your option) any later version.

 This code is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 Lesser General Public License for more details.

 You should have received a copy of the GNU Lesser General Public
 License along with this package; if not, see 
 <http://www.gnu.org/licenses/>.
 
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
#include <netinet/ip.h>
#include <netdb.h>

//#define VHPI_DEBUG 1
//#define VHPI_GDBWAIT 1

#ifdef VHPI_DEBUG
#define d_perror(x) perror(x)
#define debug(...)  printf(__VA_ARGS__)
#else
#define d_perror(x)
#define debug(...)
#endif

// bit masks for sigentry.flags
#define FLAG_HAS_CHANGED 0x1
#define FLAG_INITIAL_VAL 0x2

// codes for update_signal return value
#define UPDATE_ERROR -1 
#define UPDATE_END    0 // end simulation
#define UPDATE_SIGNAL 1 // next update need a signal trigger or small time delay
#define UPDATE_TIME   2 // next update will be at a time delay
#define UPDATE_DELTA  3 // next update need a delta step

#define MAX_STRING 256

// static info
static int init_connection_flag = 0;
static int conn_sockfd = -1;
static int rpipe = 0;
static int wpipe = 0;

static char cosim_from_signals[MAX_STRING];
static char cosim_to_signals[MAX_STRING];
static int cosim_init_flag = 0;

static uint64_t vhdl_time_res = 0;
static uint64_t vhdl_curtime = 0;
static uint64_t myhdl_curtime = 0;
static uint64_t myhdl_next_trigger = 0;

// string object from GHDL
struct int_bounds {
  int left;
  int right;
  char dir;
  unsigned int len;
};

typedef struct ghdl_string_s {
  char *base;
  struct int_bounds *bounds;
} ghdl_string;

typedef struct ghdl_int_array_s {
  uint32_t *base;
  struct int_bounds *bounds;
} ghdl_int_array;

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
static int init_connection();
static int init_unix_socket(char * socket_path);
static int init_inet_socket(char * socket_path);
static void d_print_rawdata(uint32_t * data, int len, char * premsg);
static void d_print_sigset(sigentry_t * base, int len, char * premsg);
static int parse_init(char * input);
static int sendrecv(char * buf, int max_len);
void intseq_to_signals(uint32_t * datain);

int startup_simulation (uint64_t time, uint64_t time_res, ghdl_string * from_signals, ghdl_string * to_signals);
int update_signal (ghdl_int_array * datain, ghdl_int_array * dataout, uint64_t time);
uint64_t next_timetrigger(uint64_t curtime);

static int init_connection()
{
    char *s;
    char *w;
    char *r;
    int sockfd;

    if (init_connection_flag) {
        return 0;
    }
    
    s = getenv("MYHDL_SOCKET");
    w = getenv("MYHDL_TO_PIPE");
    r = getenv("MYHDL_FROM_PIPE");
    
    if (s != NULL) {
        // sockets available, use as first choice
        
        /* format for socket path:
         <hostname>:<port> for IP sockets
         <filepath> for unix sockets (assume full path)
         */ 
        if(strchr(s, ':') != NULL) {
            // format candidate for inet socket
            sockfd = init_inet_socket(s);
        } else {
            // assume UNIX sockets
            sockfd = init_unix_socket(s);
        }
        // if any error ocurred before, was already reported
        if(sockfd < 0) return -1;
        conn_sockfd = sockfd;
        
    } else if ((w != NULL) && (r != NULL)) {
        // fallback to unix pipes
        wpipe = atoi(w);
        rpipe = atoi(r);
        debug("DEBUG: setup pipes done.\n");
    } else {
        debug("VHPI: unable to set a connection with MyHDL.\n");
        return -1;
    }
    
    init_connection_flag = 1;
    return 0;
}

static int init_unix_socket(char * socket_path)
{
    int sockfd;
    struct sockaddr_un unix_addr;
    
    sockfd = socket(PF_UNIX, SOCK_STREAM, 0);
    if(sockfd < 0) {
        d_perror("socket");
        debug("VHPI: error on UNIX socket\n");
        return -1;
    } 
    
    unlink(socket_path);
    unix_addr.sun_family = AF_UNIX;
    snprintf(unix_addr.sun_path, UNIX_PATH_MAX, socket_path);
    
    if (connect(sockfd, (struct sockaddr *) &unix_addr, sizeof(unix_addr)) == -1) {
        d_perror("connect");
        debug("VHPI: UNIX socket, error on connect\n");
        close(sockfd);
        return -1;
    }
    debug("DEBUG: setup UNIX socket done (%s).\n", socket_path);
    return sockfd;
}

static int init_inet_socket(char * socket_path)
{
    int retval, sockfd, hostlen;
    char hostname[MAX_STRING], portname[MAX_STRING];
    char *bufptr;
    struct addrinfo * result;
    
    bufptr = strrchr(socket_path, ':');
    hostlen = (int) (bufptr - socket_path);
    strncpy(hostname, socket_path, hostlen);
    bufptr++;
    strncpy(portname, bufptr, hostlen);
    
    retval = getaddrinfo(hostname, portname, NULL, &result);
    
    if(retval < 0) {
        debug("VHPI: error on INET getaddrinfo (reason: %s).\n", gai_strerror(retval));
        return -1;
    } 
    
    if(result->ai_family == AF_INET) {
        sockfd = socket(PF_INET, SOCK_STREAM, 0);
    } else if(result->ai_family == AF_INET6) {
        sockfd = socket(PF_INET6, SOCK_STREAM, 0);
    } 
    
    if(sockfd < 0) {
        d_perror("socket");
        debug("VHPI: error on INET socket creation.\n");
        freeaddrinfo(result);
        return -1;
    } 
    
    if (connect(sockfd, result->ai_addr, result->ai_addrlen) == -1) {
        d_perror("connect");
        debug("VHPI: error on INET connect.\n");
        close(sockfd);
        freeaddrinfo(result);
        return -1;
    }
    debug("VHPI: INET socket (%s) done. sockfd=%d .\n", socket_path, sockfd);
    
    freeaddrinfo(result);    
    return sockfd;
}

#ifdef VHPI_DEBUG
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
#else
static void d_print_rawdata(uint32_t * data, int len, char * premsg)
{
    return;
}

static void d_print_sigset(sigentry_t * base, int len, char * premsg)
{
    return;
}
#endif


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
        if(sscanf(token, "%ld", &tmpnumber) < 0) break;
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
    
    if(conn_sockfd > 0) {
        retval = send(conn_sockfd, buf, nbytes, MSG_NOSIGNAL);
    } else {
        retval = write(wpipe, buf, nbytes);
    }
    
    if(retval <= 0) {
        // check for EPIPE error: simply return 0 bytes read
        if(errno == EPIPE) return 0;
        d_perror("send");
        debug("VHPI: error on send (%d)\n", retval);
        return retval;
    }
    
    if(conn_sockfd > 0) {
        nbytes = recv(conn_sockfd, buf, max_len, MSG_NOSIGNAL);
    } else {
        nbytes = read(rpipe, buf, max_len);
    }
    
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
                tmpvalue = datain[intidx];
                tmpvalue >>= bitidx;
                tmpvalue &= ((1 << (size - dif)) - 1);
                intidx++;
                if(intidx >= cosim_ts_bytesize) break;
                // second part
                tmpvalue |= (datain[intidx] & ((1 << dif) - 1)) << (size - dif);
                bitidx = dif;
            } else {
                tmpvalue = datain[intidx];
                tmpvalue >>= bitidx;
                tmpvalue &= (1 << size) - 1;
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
                    tmpvalue = datain[intidx];
                    tmpvalue >>= bitidx;
                    tmpvalue &= ((1 << (size - dif)) - 1);
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

// ***** external interface to myhdl_vhpi_core *****

/** startup_simulation
 * called on the start of simulation
 * 
 */
int startup_simulation (uint64_t time, uint64_t time_res, ghdl_string * from_signals, ghdl_string * to_signals)
{
    int retval, i, nbytes;
    char buf[MAX_STRING];
    char *bufptr, *token;
    
    debug("VHPI: startup_simulation:\n time = %ld\n time_res = %ld\n from_signals = <%s>\n to_signals = <%s>\n", (unsigned long) time, (unsigned long) time_res, from_signals->base, to_signals->base);
    
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
    
    debug("VHPI: PID = %d\n", getpid());
#ifdef VHPI_GDBWAIT
    debug("VHPI: Waiting 10 seconds to gdb attach.\n");
    sleep(10);
    debug("VHPI: ... Done. You should be gdb attached now.\n");
#endif
    
    retval = init_connection();
    if(retval < 0) return retval;
    
    strncpy(cosim_from_signals, from_signals->base, MAX_STRING);
    strncpy(cosim_to_signals, to_signals->base, MAX_STRING);
    
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
                debug("VHPI: malloc error.\n");
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
                debug("VHPI: malloc error.\n");
                return -1;
            }
        }
        // bitsize increment
        cosim_ts_bitsize += cosim_to_set[i].size;
    }
    cosim_ts_bytesize = (cosim_ts_bitsize / 32) + 1;
    
    debug("VHPI: FROM %d signals => %d bits in %d bytes\n", cosim_fs_count, cosim_fs_bitsize, cosim_fs_bytesize);
    debug("VHPI: TO %d signals => %d bits in %d bytes\n", cosim_ts_count, cosim_ts_bitsize, cosim_ts_bytesize);
    
    snprintf(buf, MAX_STRING, "FROM %ld %s ", (unsigned long) time, cosim_from_signals);
    
    nbytes = sendrecv(buf, MAX_STRING);
    if(nbytes <= 0) return retval;
    
    // check for OK
    if((buf[0] != 'O') && (buf[0] != 'K')) {
        debug("VHPI: error, MyHDL returned (%s).\n", buf);
        return -1;
    }
    
    snprintf(buf, MAX_STRING, "TO %ld %s ", (unsigned long) time, cosim_to_signals);
    
    nbytes = sendrecv(buf, MAX_STRING);
    if(nbytes <= 0) return retval;
    
    if((buf[0] != 'O') && (buf[0] != 'K')) {
        debug("VHPI: error, MyHDL returned (%s).\n", buf);
        return -1;
    }
    
    // send start
    snprintf(buf, MAX_STRING, "START ");
    
    nbytes = sendrecv(buf, MAX_STRING);
    if(nbytes <= 0) return retval;
    
    if((buf[0] != 'O') && (buf[0] != 'K')) {
        debug("VHPI: error, MyHDL returned (%s).\n", buf);
        return -1;
    }
    
    debug("VHPI: startup_simulation: return 0\n");
    
    return 0;
}

/** update_signal
 * called on a change event on datain signals
 * 
 */
int update_signal (ghdl_int_array * datain, ghdl_int_array * dataout, uint64_t time)
{
    int retval, nbytes, i, j, valbytes, valindex;
    char buf[MAX_STRING];
    char val[MAX_STRING];
    char * bufptr, *valptr, *token;
    
    uint64_t myhdl_temptime;
    
    debug("VHPI: update_signal:\n datain = %p\n dataout = %p\n time = %ld\n", datain, dataout, (unsigned long) time);
    
    retval = init_connection();
    if(retval < 0) return UPDATE_ERROR;
    
    d_print_rawdata(datain->base, cosim_ts_bytesize, "datain");
    
    // convert datain to signal values (to put in TO signal set)
    intseq_to_signals(datain_ptr);
    
    d_print_sigset(cosim_to_set, cosim_ts_count, "TO_set");
    
    // prepare time counter
    vhdl_curtime = time;
    myhdl_temptime = time / vhdl_time_res;
    nbytes = snprintf(buf, MAX_STRING, "%ld ", (unsigned long) myhdl_temptime);
    debug("VHPI: prev_myhdl_time = %ld , myhdl_time = %ld\n", (unsigned long) myhdl_curtime, (unsigned long) myhdl_temptime);
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
    sscanf(token, "%ld", (unsigned long *) &myhdl_temptime);
    debug("VHPI: cur_myhdl_time = %ld , next_myhdl_time = %ld\n", (unsigned long) myhdl_curtime, (unsigned long) myhdl_temptime);
    
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
        signals_to_intseq(dataout->base);
        retval = UPDATE_SIGNAL;
    }
    
    d_print_rawdata(dataout->base, cosim_fs_bytesize, "dataout");
    
    // time check
    if(myhdl_temptime > myhdl_curtime) {
        debug("VHPI: myhdl call for time step to %ld.\n", (unsigned long) myhdl_temptime);
        myhdl_next_trigger = myhdl_temptime;
        retval = UPDATE_TIME;
    }
    
    // hack: update outputs on time 0 
    if((retval == UPDATE_DELTA) && (vhdl_curtime == 0)) {
        for(i = 0; i < cosim_ts_count; i++) {
            if(cosim_to_set[i].flags & FLAG_INITIAL_VAL) {
                cosim_to_set[i].flags |= FLAG_HAS_CHANGED;
                cosim_to_set[i].flags &= ~FLAG_INITIAL_VAL;
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
    
    debug("VHPI: next_timetrigger: temp_time %ld\n", (unsigned long) myhdl_temptime);
    
    if(myhdl_next_trigger > myhdl_temptime) {
        delta = (myhdl_next_trigger - myhdl_temptime) * vhdl_time_res;
        debug("VHPI: next_timetrigger: next VHDL trigger in %ld\n", (unsigned long) delta);
        return delta;
    } else {
        return vhdl_time_res;
    }
}
