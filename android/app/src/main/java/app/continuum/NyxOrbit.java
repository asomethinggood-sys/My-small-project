package app.continuum;

import android.animation.ValueAnimator;
import android.content.Context;
import android.graphics.*;
import android.view.View;
import android.view.MotionEvent;
import android.view.ViewConfiguration;

/** Small, finite state transitions; only connecting rotates. Stops when off-screen. */
public final class NyxOrbit extends View {
    private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
    private ValueAnimator animator,returnAnimator;
    private int phase=-1;
    private float progress=1,angle=0,touchX=0,touchY=0,downX,downY;
    private boolean dragged;
    private final int line=0xff334146,accent=0xffc2dfcc,muted=0xff7c8c90;
    public NyxOrbit(Context context){super(context);setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_YES);}
    private float dp(float v){return v*getResources().getDisplayMetrics().density;}
    public void phase(int next){if(phase==next)return;phase=next;setContentDescription(next==2?"VPN connected":next==1?"Connecting":next==3?"Disconnecting":"VPN disconnected");animateState();}
    private void animateState(){
        if(animator!=null){animator.cancel();animator=null;}
        progress=1;angle=0;
        if(!isAttachedToWindow()||getWindowVisibility()!=VISIBLE||!isShown()||!ValueAnimator.areAnimatorsEnabled()){invalidate();return;}
        final boolean busy=phase==1;
        long duration=busy?1800:420;
        animator=ValueAnimator.ofFloat(0,1);animator.setDuration(duration);
        animator.setInterpolator(new android.view.animation.LinearInterpolator());
        if(busy)animator.setRepeatCount(ValueAnimator.INFINITE);
        animator.addUpdateListener(a->{float raw=(float)a.getAnimatedValue();progress=busy?1:RustCore.motionProgress((long)(raw*duration),duration,false)/1000f;angle=busy?raw*360:0;invalidate();});
        animator.start();
    }
    @Override protected void onAttachedToWindow(){super.onAttachedToWindow();animateState();}
    @Override protected void onDetachedFromWindow(){if(animator!=null){animator.cancel();animator=null;}if(returnAnimator!=null){returnAnimator.cancel();returnAnimator=null;}touchX=touchY=0;super.onDetachedFromWindow();}
    @Override protected void onWindowVisibilityChanged(int visibility){super.onWindowVisibilityChanged(visibility);if(paint!=null)animateState();}
    @Override protected void onVisibilityChanged(View changed,int visibility){super.onVisibilityChanged(changed,visibility);if(paint!=null)animateState();}
    @Override public boolean onTouchEvent(MotionEvent event){
        switch(event.getActionMasked()){
            case MotionEvent.ACTION_DOWN:
                if(returnAnimator!=null){returnAnimator.cancel();returnAnimator=null;}
                downX=event.getX();downY=event.getY();dragged=false;return true;
            case MotionEvent.ACTION_MOVE:
                float dx=event.getX()-downX,dy=event.getY()-downY;
                if(Math.abs(dx)>ViewConfiguration.get(getContext()).getScaledTouchSlop()&&Math.abs(dx)>Math.abs(dy)){
                    dragged=true;getParent().requestDisallowInterceptTouchEvent(true);
                }
                if(dragged){float max=dp(12);touchX=Math.max(-max,Math.min(max,dx*.18f));touchY=Math.max(-max,Math.min(max,dy*.18f));invalidate();}
                return true;
            case MotionEvent.ACTION_UP:
                if(!dragged)performClick();
                releaseTouch();return true;
            case MotionEvent.ACTION_CANCEL:
                releaseTouch();return true;
            default:return true;
        }
    }
    @Override public boolean performClick(){super.performClick();return true;}
    private void releaseTouch(){
        if(getParent()!=null)getParent().requestDisallowInterceptTouchEvent(false);
        if(!ValueAnimator.areAnimatorsEnabled()){touchX=touchY=0;invalidate();return;}
        final float fromX=touchX,fromY=touchY;
        returnAnimator=ValueAnimator.ofFloat(1,0);returnAnimator.setDuration(300);
        returnAnimator.setInterpolator(new android.view.animation.DecelerateInterpolator());
        returnAnimator.addUpdateListener(a->{float fraction=(float)a.getAnimatedValue();touchX=fromX*fraction;touchY=fromY*fraction;invalidate();});
        returnAnimator.start();
    }
    @Override protected void onDraw(Canvas c){
        super.onDraw(c);float x=getWidth()/2f,y=getHeight()/2f,r=Math.min(getWidth(),getHeight())*.37f;
        // A lightweight translucent surface with touch-driven parallax; not a
        // system blur or a claim to reproduce any particular OS material.
        paint.setStyle(Paint.Style.FILL);
        paint.setShader(new RadialGradient(x-r*.35f+touchX,y-r*.45f+touchY,r*1.7f,
                new int[]{0x663f5a59,0x332d4143,0x11111b20},null,Shader.TileMode.CLAMP));
        c.drawCircle(x,y,r,paint);paint.setShader(null);
        paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(dp(1));paint.setColor(line);paint.setStrokeCap(Paint.Cap.ROUND);
        c.drawCircle(x,y,r,paint);
        for(int i=0;i<12;i++){double a=Math.toRadians(i*30);float l=i%3==0?dp(6):dp(3);c.drawLine(x+(r+dp(9))*(float)Math.cos(a),y+(r+dp(9))*(float)Math.sin(a),x+(r+dp(9)+l)*(float)Math.cos(a),y+(r+dp(9)+l)*(float)Math.sin(a),paint);}
        paint.setColor(phase==2?accent:muted);paint.setStrokeWidth(dp(2));
        if(phase==2||phase==1)c.drawArc(x-r,y-r,x+r,y+r,-90+angle,phase==2?360*progress:75,false,paint);
        // A custom crescent, not an asset or an imitation of a system power icon.
        float m=dp(29),shift=dp(13);Path moon=new Path();
        moon.addCircle(x+touchX,y+touchY,m,Path.Direction.CW);Path cut=new Path();cut.addCircle(x+touchX+shift,y+touchY-dp(10),m*.91f,Path.Direction.CW);moon.op(cut,Path.Op.DIFFERENCE);
        paint.setStyle(Paint.Style.FILL);paint.setColor(phase==2?accent:0xffe4e9e5);paint.setAlpha((int)(180+75*progress));c.drawPath(moon,paint);paint.setAlpha(255);
        if(phase==2){paint.setColor(accent);c.drawCircle(x,y-r,dp(4),paint);}
    }
}
